"""A9.16 decision-application matrix: every owner decision id of A9.8 .. A9.15 -> how it is applied to the artifacts.

Owner instruction 2026-10-01 'continue implementing them sequentially' (A9.16 step 1). One entry per decision id with
an overall status from the closed vocabulary STATUSES, the artifact applications (artifact path + record locations +
commit), and residual items (blocked / pending parts). Lane applications come from the A9.16 step-1 lane results
(commit of each lane); every one is verified at build time: the question id must occur in the lane artifact (fail
closed). Integration applications are read from the integration artifacts' owner_answers_applied rows. Nothing here
answers a question; decision files are only read (pinned through a9_16_lib and, for A9.17 .. A9.21, a9_later_lib).

Later owner decisions A9.17 .. A9.21: one entry per decision item (a9_later_lib.item_keys); A9.19 / A9.20 (one flight
configuration hall_icp_neutralizer, Xe contingency / emergency, no hollow cathode; C1 a ground-only laboratory
reference) and A9.21 (open items + hardware programme). Earlier entries a later decision amends carry
'amended_by_later'; the ones it supersedes (OQ-A907-07, MPQ-01: no C1 flight variant) get SUPERSEDED_BY_LATER_DECISION.
A9.21 AL08: APPLIED where the mass / power v3 AL-08 line and Xe v3 XV3-IF-02 carry a9_21_status
PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN (checked structurally in the artifacts); the quotation re-base stays PENDING_EVIDENCE.
A9.21 ICP_GATE: APPLIED where the RVM owner_approved_gates and the F9 pre_lock1_gates register GNG-ICP-01 (NOT_EVALUATED,
fail closed; checked structurally); the GO / NO-GO criteria stay PENDING_OWNER_ACCEPTANCE.
A9.14 S9.4 / M16-V3-Q-01: the BLOCKED residual 're-derivation of M16 scheduler blocking items (M16 v5 refresh)' is
APPLIED by M16 v5 (docs/experiments/hall_icp/integration/m16_v5; structural check of its owner_answers_applied record;
kept on the entry as 'resolved_residual'); named persons stay PENDING_EVIDENCE (staffing ledger, owner).
AG-15: the registration and RVM re-base parts are APPLIED (docs/requirements/rfp_official + rvm re-base); the owner
closed AG-15 in A9.22 G3 ('ag_15' on F9-OQ-03: owner_acceptance APPLIED, verified against the RVM closure record
rfp_rebase.ag15_closure, the registration owner_page_review and the F9 AG-15 gate; fail closed). The earlier
PENDING_OWNER_ACCEPTANCE residuals (F9-OQ-03, OD12, A9.17 RFP) are kept as 'resolved_residual' history.
A9.22: G3 APPLIED (AG-15 closure lane); G1, G2, G4 .. G9 APPLIED by their own governed migration lanes (structural
record checks / artifact tokens, commits from this branch's history); residuals: G2 Option 2 is a later change needing a
separate owner approval (LATER_SEPARATE_OWNER_APPROVAL), G9 release upload PENDING_OWNER_UPLOAD.

    python docs/decisions/application/build_a9_16_application_matrix.py          # write JSON + MD
    python docs/decisions/application/build_a9_16_application_matrix.py --check  # verify both are current
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import a9_16_lib as L  # noqa: E402
import a9_later_lib as X  # noqa: E402

OUT_JSON = HERE / "a9_16_application_matrix.json"
OUT_MD = HERE / "a9_16_application_matrix.md"
REL = lambda p: Path(p).resolve().relative_to(ROOT).as_posix()

STATUSES = {
    "APPLIED": "applied to the governing artifact(s) (artifact path + record locations + commit)",
    "NOT_APPLICABLE_TO_ARTIFACTS": "no artifact change is required now (reason given); registered in state v5",
    "PENDING_STEP_2_MODEL_CHANGE": "A9.9 production-model change, authorised; implemented in A9.16 step 2",
    "PENDING_STEP_3_ARCHITECTURE": "A9.13 decision whose application changes design-synthesis / optimizer code; "
                                   "record-level parts applied where listed; code in A9.16 step 3",
    "PENDING_CI_CHANGE": "needs a CI workflow change (.github/workflows), outside every A9.16 step-1 allowed path",
    "BLOCKED": "cannot be applied yet (missing input or record outside the allowed paths; named in 'residual')",
    "PARTIAL": "the decision's rule is recorded in the governing artifact but a named part it requires (a selection, a "
               "registration) is still pending - not APPLIED until that part exists (named in 'residual')",
    "SUPERSEDED_BY_LATER_DECISION": "applied earlier and superseded by a later owner decision (named in "
                                    "'amended_by_later'); the later decision's entry governs",
    "PENDING_GOVERNED_MIGRATION": "owner-approved migration item (A9.22 layer separation) not yet applied: its own "
                                  "governed migration lane applies it; no artifact is claimed here (named in "
                                  "'residual')",
}
RESIDUAL_STATUSES = ("BLOCKED", "PENDING_STEP_2_MODEL_CHANGE", "PENDING_STEP_3_ARCHITECTURE", "PENDING_EVIDENCE",
                     "PENDING_GOVERNED_MIGRATION", "PENDING_OWNER_UPLOAD", "LATER_SEPARATE_OWNER_APPROVAL",
                     "PENDING_CI_CHANGE", "OPEN_OWNER_QUESTION", "PENDING_FINALIZE_DESIGN_REGEN",
                     "PENDING_OWNER_ACCEPTANCE")

# ------------------------------------------------------------------------------- A9.16 step 2 / step 3 / finalize
# Applications made after step 1 (step-2 production-model commits, step-3 design-layer / RVM re-base / Rust parity v2
# commits, A9.17 data-artifact and A9.18 golden commits). Each is verified at build time: every locator token must occur
# verbatim in the artifact text (fail closed); the tokens are recorded as the record locations.
DESIGN_LAYER_COMMIT = "85342339c43962c3383fbb58f025e7ea35b0ef4f"     # A9.16 step 3 design layer (abep_sim/design)
RVM_REBASE_COMMIT = "22b539bbbcbc101baa5bdffdce6b6cc402c8d69e"       # A9.16 step 3 RVM re-base on the registered RFP
F_REGEN = ("the F-lane records that carry this decision (docs/design_synthesis/** F1-F4 / F7-F8 outputs, F9) are "
           "regenerated by the A9.16 finalize design lane (outside this lane's paths); at the base of this matrix they "
           "pre-date the step-3 design-layer code")
F_REGEN_WHERE = "docs/design_synthesis/**, docs/architecture/** (A9.16 finalize design regeneration lane)"


def _app(lane, artifact, commit, tokens, what, record=None, pin=None):
    a = {"lane": lane, "artifact": artifact, "commit": commit, "tokens": list(tokens), "what": what}
    if record:
        a["record"] = record   # structural check of the artifact record (JSON list pointer, match, field checks)
    if pin:
        a["pin"] = pin         # (JSON pointer, repo path): the value at the pointer must be the file's current sha256
    return a


CODE_APPS = {
    # ---- A9.9 (step 2, merged f9f4749)
    "F1Q-01": [_app("STEP2", "abep_sim/intake_tpmc.py", "1eb7875f65914e26755ec8473106c6bcc2e67874",
                    ["A9.9 S2.1 / F1Q-01"], "IntakeSurface species recombination by physical definitions"),
               _app("STEP2", "docs/HISTORY.md", "1eb7875f65914e26755ec8473106c6bcc2e67874",
                    ["A9.9 S2.1 F1Q-01: IntakeSurface species recombination by physical definitions"],
                    "HISTORY entry (pre-fix result preserved; regression tests)")],
    "F1Q-04": [_app("STEP2", "abep_sim/intake_surface_v2_spec.py", "530f3488a23b25788243e539adc25bc1bbd880d2",
                    ["A9.9 S2.2 (F1Q-04)"], "intake surface v2 build specification; v1 fail-closed domain")],
    "OQ-F3-01": [_app("STEP2", "abep_sim/rotor_strength.py", "5a8b77e81419b58f0b9362795b4aca1403c35c9a",
                      ["A9.9 S2.3 (OQ-F3-01) + S2.5 MCC-03"], "registered rotor-strength basis, fail closed")],
    "UPSTREAM_ICD-Q7": [_app("STEP2", "abep_sim/compressor.py", "8a7530f61c73a8a01785c3f8030c2751df083c18",
                             ["G-03 (owner decision A9.9 S2.4)"], "G-03 DragCompressor convergence fields"),
                        _app("STEP2", "abep_sim/reservoir.py", "8a7530f61c73a8a01785c3f8030c2751df083c18",
                             ["G-04 (owner decision A9.9 S2.4)"], "G-04 Reservoir steady-state convergence fields"),
                        _app("STEP2", "abep_sim/archengine.py", "f9264450d9a609ce85e8f025ab4eb92fd7d292c6",
                             ["G-03..G-05 (A9.9 S2.4)"], "non-converged gas-path states refused (fail closed)"),
                        _app("STEP2", "docs/HISTORY.md", "8a7530f61c73a8a01785c3f8030c2751df083c18",
                             ["A9.9 S2.4 (UPSTREAM_ICD-Q7): G-03..G-05 gas-path convergence flags"], "HISTORY entry")],
    "F9-OQ-04": [_app("STEP2", "abep_sim/intake_tpmc.py", "153c013de40b9d9f52e1a55605cd6291e3f1fa45",
                      ["owner decision A9.9 S2.5: MCC-05 / MCC-06 / MCC-07"], "MCC-05/06/07 input validation"),
                 _app("STEP2", "abep_sim/archengine.py", "1052253a75b36da69d6f43c8d94e450576fa644e",
                      ["S2.5 MCC-02"], "MCC-02 Gaede stage-capacity domain, no silent K clipping"),
                 _app("STEP2", "docs/HISTORY.md", "153c013de40b9d9f52e1a55605cd6291e3f1fa45",
                      ["A9.9 S2.5 (F9-OQ-04): MCC-05/06/07 intake_tpmc input validation"], "HISTORY entry")],
    # ---- A9.13 (step 3 design layer, merged 323939b)
    **{q: [_app("STEP3", "abep_sim/design/filter_stage.py", DESIGN_LAYER_COMMIT, [tok], what),
           _app("STEP3", "abep_sim/design/upstream_a9_13.py", DESIGN_LAYER_COMMIT, [tok], "DECISIONS['A9.13'].ids")]
       for q, tok, what in (
           ("F2-OQ-01", "S6.3 / F2-OQ-01", "filter baseline protection functions"),
           ("F2-OQ-02", "S6.4 / F2-OQ-02", "catalytic O->O2 element as a separate research variant"),
           ("F2-OQ-03", "S6.5 / F2-OQ-03", "FC-00 'none' a reference bound only"),
           ("F2-OQ-04", "S6.6 / F2-OQ-04", "F2 filter-stage decision S6.6"),
           ("UPSTREAM_ICD-Q1", "S6.19 / UPSTREAM_ICD-Q1", "filter a separate production-path element"))},
    "OQ-F3-02": [_app("STEP3", "abep_sim/design/compressor_synthesis.py", DESIGN_LAYER_COMMIT, ["S6.7 / OQ-F3-02"],
                      "hub ratio and blade span explicit geometry variables")],
    "OQ-F3-03": [_app("STEP3", "abep_sim/design/compressor_synthesis.py", DESIGN_LAYER_COMMIT, ["S6.8 / OQ-F3-03"],
                      "NOT_EVALUATED_OUT_OF_DOMAIN above 0.1 Pa"),
                 _app("STEP3", "abep_sim/design/plenum_feed.py", DESIGN_LAYER_COMMIT, ["S6.8 / OQ-F3-03"],
                      "compressor / plenum results above 0.1 Pa NOT_EVALUATED_OUT_OF_DOMAIN")],
    "OQ-F3-04": [_app("STEP3", "abep_sim/design/compressor_synthesis.py", DESIGN_LAYER_COMMIT,
                      ["A9.13 S6.9 / OQ-F3-04"], "rotor structural acceptance only through the registered strength "
                                                 "basis gate")],
    "OQ-F4-01": [_app("STEP3", "abep_sim/design/plenum_feed.py", DESIGN_LAYER_COMMIT, ["S6.10 / OQ-F4-01"],
                      "scheduled_operation: orbit-state-scheduled setpoint baseline, fixed setpoint fallback")],
    "OQ-F4-02": [_app("STEP3", "abep_sim/design/plenum_feed.py", DESIGN_LAYER_COMMIT, ["S6.11 / OQ-F4-02"],
                      "<= 0.1 Pa high-conductance branch labelled sensitivity / fallback")],
    "OQ-F4-03": [_app("STEP3", "abep_sim/design/plenum_feed.py", DESIGN_LAYER_COMMIT, ["S6.12 / OQ-F4-03"],
                      "transient metrics PROVISIONAL")],
    "OQ-F4-05": [_app("A9.13_DATA", "abep_sim/data/atmosphere_msis21_orbit_v1.json",
                      "2c6693a62b1a2656fab912b6947b3be4eb626165", ["A9.13 S6.14 OQ-F4-05"],
                      "orbit-resolved frozen atmosphere dataset v1 (rule-1 versioned build; orbit-averaged dataset "
                      "unchanged)"),
                 _app("A9.17", "abep_sim/data/atmosphere_msis21_hwm14_orbit_v2.json",
                      "dcd3ef945159b8657bb5547985dc04f73358c690", ["A9.17 WINDS"],
                      "relative flow / wind state: HWM14 neutral-wind dataset v2 (v1 immutable)"),
                 _app("STEP3", "abep_sim/design/upstream_a9_13.py", DESIGN_LAYER_COMMIT,
                      ["atmosphere_orbit.orbit_states"], "design-layer statewise drag / feed checks read the "
                                                         "orbit-resolved states")],
    "OQ-F78-01": [_app("STEP3", "abep_sim/design/architecture_optimizer.py", DESIGN_LAYER_COMMIT,
                       ["S6.15 / OQ-F78-01", "HC-08"], "HC-08 hard statewise T - D >= 0")],
    "OQ-F78-02": [_app("STEP3", "abep_sim/design/robust_optimizer.py", DESIGN_LAYER_COMMIT, ["S6.16 / OQ-F78-02"],
                       "scenario_robustness requires every admitted scenario"),
                  _app("STEP3", "abep_sim/design/architecture_optimizer.py", DESIGN_LAYER_COMMIT,
                       ["S6.16 / OQ-F78-02"], "require_all_admitted_scenarios")],
    "OQ-F78-03": [_app("STEP3", "abep_sim/design/architecture_optimizer.py", DESIGN_LAYER_COMMIT,
                       ["S6.17 / OQ-F78-03"], "ripple a hard feed-quality constraint (HC-12); Pareto, no weighted "
                                              "scalar"),
                  _app("STEP3", "abep_sim/design/plenum_feed.py", DESIGN_LAYER_COMMIT, ["S6.17 / OQ-F78-03"],
                       "OBJECTIVES exclude ripple")],
    "OQ-F78-04": [_app("STEP3", "abep_sim/design/upstream_a9_13.py", DESIGN_LAYER_COMMIT, ["S6.18 / OQ-F78-04"],
                       "reference spacecraft drag REFERENCE_PARAMETRIC only (reference_drag_fn)")],
    "F9-OQ-02": [_app("STEP3", "abep_sim/design/architecture_optimizer.py", DESIGN_LAYER_COMMIT,
                      ["S6.21 / F9-OQ-02", "HC-11"], "HC-11 (AG-12) statewise feed-state sufficiency, NOT_EVALUATED "
                                                    "without a validated H-1 map"),
                 _app("STEP3", "abep_sim/design/plenum_feed.py", DESIGN_LAYER_COMMIT, ["S6.21 / F9-OQ-02"],
                      "R_FLOW parametric requirement sweep only; no fixed mg/s flight gate")],
    "F9-OQ-03": [_app("STEP3", "docs/requirements/rvm_a9/rfp_rebase.py", RVM_REBASE_COMMIT,
                      ["A9.13 S6.22 F9-OQ-03", "requirement_frozen"],
                      "RVM re-based on the registered official RFP (AG-15 step); requirement_frozen stays false on "
                      "RFP rows until the owner closes AG-15")],
    # ---- A9.14
    "OD3": [_app("A9.17", "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json",
                 "fef1f6a9ed7bf513177c0d096c75dc0bfa1e5517", ["A9.14 S9.8 OD3", "A9.17 ORBIT"],
                 "design-state set v2 derived from the frozen orbit-resolved dataset only (broad envelope)")],
    "OD12": [_app("STEP3", "docs/requirements/rvm_a9/rfp_rebase.py", RVM_REBASE_COMMIT,
                  ["A9.14 OD12", "CG-N2-AO", "Compliance gate CG-IC"],
                  "compliance gates CG-IC / CG-N2-AO carry their registered RFP clauses")],
    "F0-OQ-01": [_app("A9.17", "docs/performance/dedicated_baseline_2026_10_01/REGISTRATION.json",
                      "b9b738733a6cab9cf32dcf65cf0f7f1e4a2e2855", ["s10_1_thresholds", "(A9.14 S10.1) applied unchanged"],
                      "PORT_CANDIDATE >= 60 s / MARGINAL >= 10 s applied unchanged to the dedicated baseline")],
    "F0-OQ-02": [_app("A9.17", "docs/performance/dedicated_baseline_2026_10_01/REGISTRATION.json",
                      "b9b738733a6cab9cf32dcf65cf0f7f1e4a2e2855", ["A9.14 S10.2 F0-OQ-02", "machine"],
                      "dedicated unloaded-machine baseline registered with machine / toolchain / thread metadata")],
    "RUST-OQ-02": [_app("STEP3", ".github/workflows/rust-parity.yml", "3bd06cd3d25d9a6563c1ef5f3f57ce658910ca1a",
                        ["RUST-OQ-02 = OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES"],
                        "optional Rust parity CI, fail closed on unrecorded Rust changes (normal CI unchanged)"),
                   _app("STEP3", "docs/performance/abep_core/parity_prereg_v2.json",
                        "ce5b445d2f9dc97f18f93f0b03aed693e5864add", ["RUST-OQ-02 (A9.14 S10.4"],
                        "parity pre-registration v2 (reference re-pin after A9.9)"),
                   _app("STEP3", "docs/performance/abep_core/parity_report_v2.json",
                        "d87d217d3306cc84d51d2cf7e54d9222cd52994e", ["ADMITTED"],
                        "parity campaign v2 report (all five kernels ADMITTED)")],
}
# A9.14 S9.4 / M16-V3-Q-01 residual (scheduler re-derivation, M16 v5 refresh): applied by the M16 v5 record (commit
# below, made before this matrix so the pointer is verifiable); structural record check of its owner_answers_applied
M16V5_REL = "docs/experiments/hall_icp/integration/m16_v5/subsystem_maturity_v5.json"
M16V5_COMMIT = "c4062e0fad73b7159fed109516ec8d9ffae76915"
M16V5_RESIDUAL_TEXT = ("re-derivation of M16 scheduler blocking items from the A9.8 .. A9.15 answers (M16 v5 refresh) is "
                       "not built in A9.16; M16 v4 was regenerated only for its changed RVM inputs (RFP re-base)")
CODE_APPS["M16-V3-Q-01"] = [
    _app("M16_V5", M16V5_REL, M16V5_COMMIT, ['"subsystem_maturity_v5"', '"rederivation": "APPLIED"'],
         "M16 v5: every v4 row's scheduler blocking items re-derived from the owner answers A9.8 .. A9.21 (state v5), the "
         "A9.21 programme order and GNG-ICP-01 (removed blockers with answer pointer + sha256; remaining blockers by "
         "category; no readiness advance without determining evidence); M16 v4 byte-identical; named persons stay "
         "PENDING_EVIDENCE (staffing ledger, owner; none fabricated)",
         {"list": "/owner_answers_applied", "match": ("question_id", "M16-V3-Q-01"),
          "checks": {"rederivation": ("equals", "APPLIED"), "rows_covered": ("equals", 21),
                     "decision_code": ("equals", "ACCEPT_ROLE_MAP_NAMES_FROM_STAFFING_LEDGER"),
                     "named_persons": ("startswith", "PENDING_EVIDENCE")}})]
# residual items resolved since the A9.16 matrix (kept as history on the entry: what it was, how it was resolved)
RESOLVED_RESIDUAL = {
    "M16-V3-Q-01": [{"status_before": "BLOCKED", "what": M16V5_RESIDUAL_TEXT,
                     "where_before": "docs/experiments/hall_icp/integration/ (M16 v5, not started)",
                     "status": "APPLIED", "artifact": M16V5_REL, "commit": M16V5_COMMIT}],
}
# A9.22 G3: the owner closed AG-15 (commit of the AG-15 closure lane: RVM closure record, registration page review,
# F9 ag15_f9 closure-record check, state v5 a9_22_g3); the residuals that waited for it are resolved (history kept)
A922_AG15_COMMIT = "e78c781c70f79fb46b903e19ab9cb1202db94595"
# A9.22 governed migration lanes (commits from this branch's history)
A922_DESIGN_SEPARATION_COMMIT = "c06c2ed7b95fc7b6fbc6eb38a9d66b908174bbe0"   # G2 / G5 seam; gates -> assessment
A922_PHASE_B_COMMIT = "1e4b09b9681dfa6e151f92d902ba1c2a93f6a5af"             # G6 / G7 raw / assessment split
A922_CONFIG_COMMIT = "2cbe2ddc69ac8ed786ef0bf5975e1f8ed63aa4cf"              # Phase A config (G5 mission_domain)
A922_G1_COMMIT = "512d704950946bdc0c4e55078c1a5527f75da449"                  # G1 governed baseline change
A922_G1_SYSTEM_COMMIT = "f2ebdb7bcf6e977c00f7d201abcf1ee7619ba9ed"           # G1 system.py completion
A922_G4_COMMIT = "58309a115b768e4268a9dba7993778b163fbc399"                  # G4 cathodeless active golden
A922_G8_STAGE1_COMMIT = "5dbcb539a4372450629bb7b498fb8ec8d7478cf2"           # G8 stage 1 (v2 + inventory)
A922_G8_STAGE2_COMMIT = "a5294a766e1c58cb78eeba4287064e08378c52f1"           # G8 stage 2 migration record
A922_G9_COMMIT = "3b2072e324cd121f2d2a7d7ae1df1e4a23dc40d8"                  # G9 F1 core view + archive manifest
AG15_CLOSURE_POINTER = "/rfp_rebase/ag15_closure"
AG15_CLOSURE_TOKENS = ['"ag15_closure"', '"decision_code": "AG15_CLOSED"', '"requirements_snapshot": "FROZEN"']
_AG15_RESOLVED = lambda what: [{"status_before": "PENDING_OWNER_ACCEPTANCE", "what": what,   # noqa: E731
                                "where_before": "owner act (AG-15 closure)", "status": "APPLIED",
                                "artifact": "docs/requirements/rvm_a9/rvm_a9_v1.json", "commit": A922_AG15_COMMIT,
                                "record_pointer": AG15_CLOSURE_POINTER, "by": "A9.22 G3_REQUIREMENTS_SNAPSHOT"}]
RESOLVED_RESIDUAL_AG15 = {
    "F9-OQ-03": _AG15_RESOLVED("AG-15 closure: the official RFP is registered by sha256 (A9.17 RFP) and the RVM is "
                               "re-based on it (step 3) - both APPLIED ('ag_15'); requirement_frozen stays false on "
                               "RFP rows until the owner accepts the re-base and closes AG-15"),
    "OD12": _AG15_RESOLVED("RFP clauses registered and mapped (CG-IC / CG-SPF / CG-N2-AO carry their clauses); "
                           "requirement_frozen stays false until the owner closes AG-15"),
    ("A9.17", "RFP"): _AG15_RESOLVED("AG-15 closure (requirement_frozen stays false on RFP rows until the owner accepts "
                                     "the re-base and closes AG-15)"),
}
# A9.13 step-3 decisions that are NOT applied by any step-3 / finalize commit at this matrix's base (truthfully BLOCKED)
STEP3_NOT_APPLIED = {
    "F1Q-02": "no step-3 commit applies S6.1: the F1 intake record (docs/design_synthesis/f1_intake/) still carries "
              "F1Q-02 as TBD_OWNER and no PARAMETRIC_SENSITIVITY budgeting label / pre-LOCK-1 sourced-design gate is "
              "recorded in an artifact (design-lane paths)",
    "OQ-F4-04": "no step-3 commit records the S6.13 flow-gap order (performance-derived requirement first, then "
                "capture / compression / feed / schedule); only its 'no fixed 0.38 mg/s flight requirement' part is "
                "enforced through S6.21 (plenum_feed R_FLOW sweep only); the F4 record still carries the as-raised "
                "OQ-F4-04 (design-lane paths)",
}
# A9.13 step-3 decisions applied with a part still pending (PARTIAL)
STEP3_PARTIAL = {
    "F1Q-03": ("intake_surface_v2_spec.py carries S6.2 (v2 over the registered AOCS envelope; no silent "
               "extrapolation) but the AOCS pointing envelope is not registered, so surface v2 is not built",
               [_app("STEP2", "abep_sim/intake_surface_v2_spec.py", "530f3488a23b25788243e539adc25bc1bbd880d2",
                     ["A9.13 S6.2 (F1Q-03)"], "v2 build spec covers the registered AOCS envelope; build BLOCKED until "
                                              "it is registered")]),
}
A9_9_PARTIAL = {"F1Q-04": "spec and v1 fail-closed domain implemented; the v2 surface itself is not built (BLOCKED "
                          "pending the registered AOCS pointing envelope, A9.13 S6.2 / F1Q-03)"}

# A9.17 .. A9.21 owner decisions (not in a9_16_lib.DECISIONS: adding them there would change the pins of every builder
# that imports the lib); pinned in a9_later_lib (json + verbatim md sha256); the verbatim .md governs.
LATER = tuple(X.ORDER)
# A9.19 / A9.20 application commits (in the history of this matrix's base) and the A9.17 .. A9.21 records commit of
# this lane (owner-question state v5 + M16 v4; committed before this matrix so the pointer is verifiable)
A919_RVM_COMMIT = "1eb021c91da662fe277d098cc11ab35c3d28afc7"       # RVM rows RVM-28..30, re-applied on the finalize RVM
A919_BUDGETS_COMMIT = "4cd79e6425472ece6835d4c254710cdfe036b31a"   # mass / power v3 + Xe v3 A9.19 / A9.20
A919_DESIGN_COMMIT = "90f0137842ddd59dcfc99444fc98ba46c808edd0"    # abep_sim/design/a9_19_architecture.py (adds FLIGHT_CONFIGURATIONS)
A919_INTEGRATION_COMMIT = "f280cf4401fe1f428352b5657e97881f38cc7c79"  # F9 Xe role, H2-6 live-source CI check
RECORDS_A917_21_COMMIT = "42453f5fdb10a645ea88ef90f56aad851d2c6520"  # state v5 + M16 v4 A9.17 .. A9.21 records
A921_AL08_BUDGETS_COMMIT = "6a69ac52dcca091212c0dfc4cd10abcbd2e1bdcc"  # mass / power v3 AL-08 + Xe v3 XV3-IF-02 A9.21 label
A921_ICP_GATE_COMMIT = "eae96c820ef86c281dc7ffafd6bb698ee0b2b96f"      # RVM + F9 GNG-ICP-01 registration (A9.21 ICP_GATE)
A921_HW_PROGRAMME_COMMIT = "364a5ab3f1d61206bce54cc1a160570e8947f185"
HW_PROGRAMME_REL = "docs/experiments/hall_icp/programme/hw_programme_a9_21_v1.json"  # programme-order record consumed by H-1, P1-P4
V5_REL = "docs/budgets/owner_decisions/owner_questions_state_v5.json"
M16_REL = "docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json"
RVM_REL = "docs/requirements/rvm_a9/rvm_a9_v1.json"
REG_REL = "docs/requirements/rfp_official/rfp_registration_v1.json"
MP3_REL = "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json"
XE3_REL = "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json"
F9_REL = "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"


AL08_LABEL = "PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN"
ICP_GATE_ID = "GNG-ICP-01"
ICP_CRITERIA = "PENDING_OWNER_ACCEPTANCE"
ICP_GATE_CHECKS = {"status": ("equals", "NOT_EVALUATED"), "criteria": ("equals", ICP_CRITERIA),
                   "placement": ("equals", "BEFORE_LOCK-1"), "mandatory": ("equals", True),
                   "lock1_release_reportable": ("equals", False)}


def _rec(artifact, tokens, what):
    return _app("A9_17_21_RECORDS", artifact, RECORDS_A917_21_COMMIT, tokens, what)


LATER_APPS = {
    ("A9.17", "WINDS"): [
        _app("A9.17", "abep_sim/data/atmosphere_msis21_hwm14_orbit_v2.json", "dcd3ef945159b8657bb5547985dc04f73358c690",
             ["A9.17 WINDS"], "atmosphere v2 with HWM14 neutral winds; v1 never overwritten"),
        _app("A9.17", "abep_sim/atmosphere_orbit_v2.py", "dcd3ef945159b8657bb5547985dc04f73358c690", ["HWM14"],
             "v2 producer / accessor (corotating and HWM14-corrected relative flow)")],
    ("A9.17", "ORBIT"): [
        _app("A9.17", "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json",
             "fef1f6a9ed7bf513177c0d096c75dc0bfa1e5517", ["A9.17 ORBIT"],
             "broad-envelope design-state set v2 (inclination / LTAN TBD from the official mission ICD; 96.3 deg / "
             "dawn-dusk CODE_DEFAULT / PARAMETRIC)")],
    ("A9.17", "DATA_SIZE"): [
        _app("A9.17", "MANIFEST.in", "ab72fbaf518e10754dc8e810844d7cc65b62eeda", ["A9.17 DATA_SIZE"],
             "one canonical compressed copy, excluded from the sdist"),
        _app("A9.17", "pyproject.toml", "ab72fbaf518e10754dc8e810844d7cc65b62eeda", ["A9.17 DATA_SIZE"],
             "excluded from the installed wheel")],
    ("A9.17", "SPUTTER"): [
        _app("A9.17", "docs/evidence/sputter_yields_v1/sputter_yields_v1.json",
             "035f257f903baebeeb3bcec49739e163f0155151", ['"decision_key": "SPUTTER"'],
             "register regenerated under E_screen 1.10 x E_th / F_worst 1.25 (screening only)")],
    ("A9.17", "RFP"): [
        _app("A9.17", "docs/requirements/rfp_official/rfp_registration_v1.json",
             "96ace704ed78d699c5805ebcc8acd99f5cc0b125", ["owner A9.17 RFP", "REGISTERED_BY_HASH_PDF_CONTROLLED_EXTERNALLY"],
             "RFP registered by sha256 with retrieval record; PDF in the controlled evidence store"),
        _app("STEP3", "docs/requirements/rvm_a9/rfp_rebase.py", RVM_REBASE_COMMIT, ["A9.17 RFP"],
             "RVM re-based on the registered clauses")],
    ("A9.17", "PERF"): [
        _app("A9.17", "docs/performance/dedicated_baseline_2026_10_01/REGISTRATION.json",
             "b9b738733a6cab9cf32dcf65cf0f7f1e4a2e2855", ['"A9.17 PERF"', "ADMISSION_BASELINE_PERFORMANCE_ONLY"],
             "dedicated owner-machine baseline registered as the Rust performance-admission baseline")],
    ("A9.18", "GOLDEN"): [
        _app("A9.18", "abep_sim/golden.py", "0192a3fc7121b95c604e7a23b9a0b0a56408dc8c",
             ["A9.18 GOLDEN = NEW_ADMISSIBLE_CONVERGED_GOLDEN", "golden_v2.json"],
             "GOLDEN_FILE = golden_v2.json; selection rule A9.18-SEL-1"),
        _app("A9.18", "abep_sim/data/golden_v2.json", "0192a3fc7121b95c604e7a23b9a0b0a56408dc8c",
             ["NONCONVERGED_REFERENCE / EXPECTED_NONCONVERGENCE"],
             "new admissible converged golden; golden_v1 point kept as nonconverged_reference fixture")],
    ("A9.18", "PERF_RERUN"): [],
    # ---- A9.19 (flight architecture) / A9.20 (C1 ground-only)
    ("A9.19", "architecture"): [
        _app("A9.19", RVM_REL, A919_RVM_COMMIT, ["RVM-28", "FLIGHT ARCHITECTURE (A9.19)"],
             "RVM-28 flight architecture row; configurations: hall_icp_neutralizer the flight architecture"),
        _app("A9.19", "abep_sim/design/a9_19_architecture.py", A919_DESIGN_COMMIT,
             ["FLIGHT_CONFIGURATIONS = (FLIGHT_CONFIGURATION,)"],
             "design layer: one flight configuration; hall_c1_reference refused as a flight configuration"),
        _rec(M16_REL, ['"flight_configurations"', '"a9_19_20"'],
             "M16 v4: one flight configuration; rows 6 / 7 / 8 / 11 labelled; requirement status split")],
    ("A9.19", "xenon_role"): [
        _app("A9.19", RVM_REL, A919_RVM_COMMIT, ["RVM-29"], "RVM-29 two supply modes, Xe contingency / emergency"),
        _app("A9.19", XE3_REL, A919_BUDGETS_COMMIT, ["CONTINGENCY_EMERGENCY"], "Xe accounting v3 Xe role"),
        _app("A9.19", F9_REL, A919_INTEGRATION_COMMIT, ["contingency / emergency role, A9.19"],
             "F9 AFC-SY-XE-01 states the A9.19 Xe role"),
        _rec(V5_REL, ['"AMENDED_IN_SCOPE_BY_A9_19"'], "state v5: XA9Q-07 / XV2Q-01 / OD6 amended on the ROLE of Xe")],
    ("A9.19", "amends/A9.15"): [
        _app("A9.19", F9_REL, A919_INTEGRATION_COMMIT, ["contingency / emergency role, A9.19"],
             "F9: the A9.15 'not a contingency' wording superseded on the role of Xe"),
        _rec(V5_REL, ['"superseded_statements_a9_19"'], "state v5: the two A9.15 statements superseded on the ROLE "
                                                         "of Xe listed with A9.19 pointer + sha256")],
    ("A9.19", "amends/A9.14 S8.33 MPQ-01 / S8.17 OQ-A907-07"): [
        _app("A9.19", MP3_REL, A919_BUDGETS_COMMIT, ["NO_C1_XE_BRANCH_IN_FLIGHT"],
             "mass / power v3: no AL-C1, no C1 electronics, no C1 Xe branch in the flight architecture"),
        _rec(V5_REL, ['"SUPERSEDED_BY_A9_19"'], "state v5: OQ-A907-07 and MPQ-01 superseded (no C1 flight variant)")],
    ("A9.19", "amends/A9 C1 CONTROL_FALLBACK"): [
        _app("A9.19", RVM_REL, A919_RVM_COMMIT, ["is not a flight fallback (A9.19)"],
             "RVM-15: CONTROL_FALLBACK sizing is not a flight fallback"),
        _rec(M16_REL, ['"SUPERSEDED_FOR_FLIGHT_PRE_A9_19"'], "M16 v4: C1 fallback statements classified as pre-A9.19 "
                                                              "history; A9.2 CONTROL_FALLBACK carried verbatim with a note"),
        _rec(V5_REL, ['"OD-XE-5"', '"R6-Q1"', '"OD-M5"', '"HWQ-09"'],
             "state v5: the C1 'reference/fallback' answers amended to the ground reference")],
    ("A9.19", "owner_request"): [
        _app("A9.19", MP3_REL, A919_BUDGETS_COMMIT, ['"c1_mass_check"'], "mass / power v3 c1_mass_check answers "
                                                                          "'check C1 mass'")],
    ("A9.20", "answer"): [
        _app("A9.20", RVM_REL, A919_RVM_COMMIT, ["RVM-30", "GROUND_ONLY_LABORATORY_REFERENCE (A9.20)"],
             "RVM-30 C1 ground-only; hall_c1_reference cells labelled ground reference"),
        _app("A9.20", XE3_REL, A919_BUDGETS_COMMIT, ["GROUND_ONLY_LAB_REFERENCE (A9.20)"],
             "Xe accounting v3: C1 Xe is ground test-campaign Xe, never flight Xe"),
        _app("A9.20", MP3_REL, A919_BUDGETS_COMMIT, ['"retired_flight_configuration_history"'],
             "mass / power v3: hall_c1_reference column retired to history"),
        _rec(M16_REL, ["NOT_A_FLIGHT_SUBSYSTEM"], "M16 v4 row 11: C1 GROUND_ONLY_LAB_REFERENCE, not a flight subsystem")],
    # ---- A9.21 (open items + hardware programme)
    ("A9.21", "PERF_RERUN"): [],
    ("A9.21", "AL08"): [
        _rec(V5_REL, ['"KEEP_6_05KG_PROVISIONAL_WAIT_FOR_QUOTES_TO_REBASE_AL08"'], "state v5 MQ-05 AMENDED_BY_A9_21"),
        _rec(M16_REL, ['"AL08"'], "M16 v4 rows 6 / 7 / 8: AL-08 provisional until quotations"),
        _app("A9.21", MP3_REL, A921_AL08_BUDGETS_COMMIT, ["KEEP_6_05KG_PROVISIONAL_WAIT_FOR_QUOTES_TO_REBASE_AL08"],
             "mass / power v3 AL-08 line: a9_21_status PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN (6.0528 kg kept as a "
             "provisional planning floor; re-based only after the split quotations)",
             {"list": "/lines/hall_icp_neutralizer", "match": ("line", "AL-08"),
              "checks": {"a9_21_status": ("startswith", AL08_LABEL)}}),
        _app("A9.21", XE3_REL, A921_AL08_BUDGETS_COMMIT, ["KEEP_6_05KG_PROVISIONAL_WAIT_FOR_QUOTES_TO_REBASE_AL08"],
             "Xe accounting v3 XV3-IF-02 (AL-08 stored-Xe hardware): a9_21_status PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN",
             {"list": "/interface_demands", "match": ("id", "XV3-IF-02"),
              "checks": {"a9_21_status": ("startswith", AL08_LABEL)}})],
    ("A9.21", "H2_6"): [
        _app("A9.21", "scripts/ci_checks.py", A919_INTEGRATION_COMMIT, ["h2_6_live_sources"],
             "live-source verification of the frozen H2-6 builder runs as a CI static check (implemented in the "
             "A9.19 / A9.20 integration, SW-02; A9.21 approves it; the H2-6 builder stays byte-identical)"),
        _app("A9.21", "docs/ci/CI.md", A919_INTEGRATION_COMMIT, ["`h2_6_live_sources`"], "CI documentation")],
    ("A9.21", "ICP_GATE"): [
        _rec(V5_REL, ['"RP-A919-01"', '"NOT_APPROVED_PRESERVED_FOR_OWNER_REVIEW"'],
             "state v5 RP-A919-01 ANSWERED_BY_A9_21 in part; criteria preserved for owner review"),
        _rec(M16_REL, ['"ICP_GATE"'], "M16 v4 row 18 carries the gate (fail closed; no numbers)"),
        _app("A9.21", RVM_REL, A921_ICP_GATE_COMMIT, ['"owner_approved_gates"', ICP_GATE_ID],
             "RVM owner_approved_gates: " + ICP_GATE_ID + " mandatory ICP go / no-go before LOCK-1 (own id, not "
             "AG-01 .. AG-15), NOT_EVALUATED (fail closed), criteria PENDING_OWNER_ACCEPTANCE; RP-A919-01 (a) - (c) "
             "preserved verbatim for owner review (never evaluated)",
             {"list": "/owner_approved_gates", "match": ("id", ICP_GATE_ID), "checks": ICP_GATE_CHECKS}),
        _app("A9.21", F9_REL, A921_ICP_GATE_COMMIT, ['"pre_lock1_gates"', '"lock1_precondition"', ICP_GATE_ID],
             "F9 pre_lock1_gates: " + ICP_GATE_ID + " re-evaluated from the RVM record (NOT_EVALUATED); LOCK-1 release "
             "not reportable while it is not GO; architecture status stays INVESTIGATION_HYPOTHESIS",
             {"list": "/pre_lock1_gates", "match": ("id", ICP_GATE_ID),
              "checks": {"current_status": ("equals", "NOT_EVALUATED"), "criteria": ("equals", ICP_CRITERIA),
                         "placement": ("equals", "BEFORE_LOCK-1"),
                         "evidence_sufficient_for_freeze": ("equals", False)}})],
    ("A9.21", "BID_CLOSE"): [
        _rec(V5_REL, ['"rfp_registered_document"'], "state v5 WEB-ACC-2 AMENDED_BY_A9_21 (operational deadline "
                                                     "05-Oct-2026 17:00; RFP number from the registered document)")],
    ("A9.21", "HW_PROGRAMME"): [
        _rec(M16_REL, ['"HW_PROGRAMME"'], "M16 v4: programme order attached to rows 9 / 10 / 11 / 13 / 15 / 18 / 19 / "
                                          "20 / 21"),
        _rec(V5_REL, ['"HW_PROGRAMME"'], "state v5: confirmations on P1Q-07, F5-OQ-01 / 02, F9-OQ-02, P1-IT-52 / 55, "
                                         "P2Q-07, P4-OQ-03"),
        _app("A9.21", "docs/experiments/hall_icp/programme/hw_programme_a9_21_v1.json", A921_HW_PROGRAMME_COMMIT,
             ['"H1-S7.1"', '"C1-REF"', '"ICP-45N"', '"ICP-XE-MODE"', '"P2-MAP"', '"P4-ACCEPTANCE-EXPOSURE"',
              '"H1-THRUST-FEED-MAP"'],
             "programme-order record: A9.21 items 6-11 as 14 ordered steps with predecessors and entry preconditions "
             "(fail closed: never PASS / GO / START_AUTHORISED; recorder readings RR-01..RR-03 for the owner)"),
        _app("A9.21", "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json", A921_HW_PROGRAMME_COMMIT,
             ["hw_programme_a9_21_v1.json"], "H-1: S7.1 FEMM points before S7.2 engineering channel point (programme "
                                             "record pinned)",
             pin=("/a9_21_programme/programme_record_sha256", HW_PROGRAMME_REL)),
        _app("A9.21", "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json", A921_HW_PROGRAMME_COMMIT,
             ["hw_programme_a9_21_v1.json"], "P1: C1 reference before P1-S7; Ar reference -> air/N2 ICP-45 -> Xe mode, "
                                             "one gas/mode per campaign with its own domain and provenance",
             pin=("/a9_21_programme/programme_record_sha256", HW_PROGRAMME_REL)),
        _app("A9.21", "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json", A921_HW_PROGRAMME_COMMIT,
             ["hw_programme_a9_21_v1.json"], "P2: map only after the in-house V/I calibration + uncertainty budget freeze",
             pin=("/a9_21_programme/programme_record_sha256", HW_PROGRAMME_REL)),
        _app("A9.21", "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json",
             A921_HW_PROGRAMME_COMMIT, ["hw_programme_a9_21_v1.json"], "P3: after coupled H-1 + ICP",
             pin=("/a9_21_programme/programme_record_sha256", HW_PROGRAMME_REL)),
        _app("A9.21", "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json", A921_HW_PROGRAMME_COMMIT,
             ["hw_programme_a9_21_v1.json"], "P4: acceptance exposure only after LOCK-2 is frozen",
             pin=("/a9_21_programme/programme_record_sha256", HW_PROGRAMME_REL))],
    ("A9.21", "EXTERNAL_INPUTS"): [
        _rec(V5_REL, ['"TBD_EXTERNAL_INPUT'], "state v5: F1Q-03, OQ-F78-04, OD3, OQ-F4-05 external_input_status"),
        _rec(M16_REL, ['"EXTERNAL_INPUTS"'], "M16 v4 row 1")],
    ("A9.21", "RFQ_DISPATCH"): [],
    # ---- A9.22 (layer separation): G3 applied by the AG-15 closure lane; the other items by their own migrations
    ("A9.22", "G3_REQUIREMENTS_SNAPSHOT"): [
        _app("A9.22", RVM_REL, A922_AG15_COMMIT, AG15_CLOSURE_TOKENS + ["RP-BRIEF-01"],
             "RVM: requirement_frozen = true on the 22 RFP_CLAUSE rows (before status evaluation; no status changed), "
             "closure record rfp_rebase.ag15_closure (RP-BRIEF-01 format), requirements snapshot FROZEN",
             {"list": "/rows", "match": ("id", "RVM-01"), "checks": {"requirement_frozen": ("equals", True)}}),
        _app("A9.22", "docs/requirements/rvm_a9/rfp_rebase.py", A922_AG15_COMMIT,
             ["A9.22 G3", "ACCEPTED_BASIS_SHA256", "def record_closure"],
             "closure applied on the final RVM; a later change of the requirements basis is refused (new owner "
             "decision needed)"),
        _app("A9.22", REG_REL, A922_AG15_COMMIT,
             ['"owner_page_review"', "OWNER_REVIEWED_NO_ADDITIONAL_TECHNICAL_PERFORMANCE_REQUIREMENT"],
             "registration page_coverage: owner review disposition of pages 1-15 / 34-40 (owner-stated, verbatim)"),
        _app("A9.22", F9_REL, A922_AG15_COMMIT, ['"owner_closure_recorded"', '"architecture_status": '
                                                 '"INVESTIGATION_HYPOTHESIS"'],
             "F9 AG-15 closed on the owner closure record (fail-closed check replaces the 'CLOSED' text prefix); "
             "architecture stays INVESTIGATION_HYPOTHESIS",
             {"list": "/architecture_gates", "match": ("id", "AG-15"),
              "checks": {"evidence_sufficient_for_freeze": ("equals", True),
                         "current_status": ("equals", "DETERMINING_EVIDENCE_PRESENT_NO_REMAINING_CONDITION")}}),
        _app("A9.22", "docs/architecture/freeze_candidate/ag15_f9.py", A922_AG15_COMMIT,
             ["def owner_closure_errors", "CLOSURE_DECISION"], "F9 AG-15 closure-record check (fail closed)"),
        _app("A9.22", V5_REL, A922_AG15_COMMIT, ['"a9_22_g3"', '"PERFORMS_OWNER_ACT"'],
             "state v5: F9-OQ-03 PERFORMS_OWNER_ACT record; a9_22_g3 with pointers + sha256")],
    # ---- A9.22 G1 / G2 / G4 .. G9: applied by their own governed migration lanes (commits on the integration history;
    # each (commit, artifact) pair is a commit that changed the artifact; structural record checks where a record exists)
    ("A9.22", "G1_MISSION_LIFE"): [
        _app("A9.22", "abep_sim/operating_inputs.py", A922_G1_COMMIT,
             ["G1_MISSION_LIFE = MISSION_DURATION_26280_H", "SUBSYSTEM_FIRING_LIFE_ASSUMPTION",
              "HISTORICAL_MISSION_HOURS_PRE_A9_22"],
             "operating-inputs seam: mission-duration basis 26,280 h (26,000 h kept as the immutable historical "
             "constant, not consumed); 15,000 h only as the labelled subsystem firing-life assumption"),
        _app("A9.22", "abep_sim/system.py", A922_G1_SYSTEM_COMMIT, ["A9.22 G1 governed baseline change"],
             "system.py completion: AO fluence / erosion, cathode starts, mission reliability horizon on 26,280 h"),
        _app("A9.22", "config/mission/mission_scenario_v1.json", A922_G1_SYSTEM_COMMIT,
             ['"authoritative_basis_h": 26280', '"g1_status": "APPLIED"'],
             "frozen mission scenario: mission_hours 26,280 h, G1 APPLIED with the migrated consumers listed",
             {"node": "/inputs/mission_hours", "checks": {"value": ("equals", 26280),
                                                          "label": ("equals", "MISSION_DURATION_BASIS"),
                                                          "g1_status": ("equals", "APPLIED")}}),
        _app("A9.22", "abep_sim/data/golden_v2.json", A922_G1_COMMIT, ["mission-duration basis 26,280 h"],
             "golden v2 regenerated under the governed baseline change (architecture_closure xe_kg on 26,280 h)",
             {"node": "/provenance/a9_22", "checks": {"G1": ("startswith", "mission-duration basis 26,280 h")}}),
        _app("A9.22", "docs/HISTORY.md", A922_G1_COMMIT, ["A9.22 G1 governed baseline change"],
             "HISTORY entries (rule 1-2 governed baseline change, logged)")],
    ("A9.22", "G2_C_DRAG_RFP"): [
        _app("A9.22", "abep_sim/design/engineering_constraints.py", A922_DESIGN_SEPARATION_COMMIT,
             ["A9.22 G2 (Option 1)", "C-DRAG-RFP", "INTAKE_DRAG_GENERATION_LIMIT_N"],
             "C-DRAG-RFP kept as an F1 GENERATION filter read from the frozen engineering-constraints seam "
             "(Option 1; numerical / design-space results preserved)")],
    ("A9.22", "G4_GOLDEN_ARCHITECTURE"): [
        _app("A9.22", "abep_sim/data/golden_v2.json", A922_G4_COMMIT,
             ['"HISTORICAL_NON_FLIGHT_REGRESSION"', '"hall_icp_neutralizer_reference"'],
             "golden v2 case roles: LaB6 / hollow-cathode cases HISTORICAL_NON_FLIGHT_REGRESSION; governed active "
             "reference case hall_icp_neutralizer_reference",
             {"node": "/case_roles", "checks": {
                 "architecture_closure": ("equals", "HISTORICAL_NON_FLIGHT_REGRESSION"),
                 "mission": ("equals", "HISTORICAL_NON_FLIGHT_REGRESSION"),
                 "hall_icp_neutralizer_reference": ("equals", "GOVERNED_REFERENCE_ACTIVE_ARCHITECTURE_PARTIAL")}}),
        _app("A9.22", "abep_sim/golden.py", A922_G4_COMMIT, ["def require_flight_eligible_case"],
             "guard: historical non-flight golden cases refused for closure / selection / budgets"),
        _app("A9.22", "abep_sim/archengine.py", A922_G4_COMMIT, ["def require_flight_eligible("],
             "guard: LaB6 / hollow-cathode architectures refused as flight-eligible"),
        _app("A9.22", "docs/HISTORY.md", A922_G4_COMMIT, ["A9.22 G4"], "HISTORY entry")],
    ("A9.22", "G5_ALTITUDE_BAND"): [
        _app("A9.22", "abep_sim/design/engineering_constraints.py", A922_DESIGN_SEPARATION_COMMIT,
             ["A9.22 G5", "MISSION_DOMAIN_ALTITUDE_KM"],
             "design seam consumes mission_domain.altitude_km = [180, 230] (no RFP clause parsing)"),
        _app("A9.22", "config/requirements/rfp_constraints_v1.json", A922_CONFIG_COMMIT,
             ['"mission_domain"', "A9.22 G5"],
             "requirements snapshot: mission_domain.altitude_km [180, 230], FROZEN, provenance RVM-01",
             {"node": "/mission_domain", "checks": {"altitude_km": ("equals", [180, 230]),
                                                    "status": ("equals", "FROZEN"),
                                                    "rvm_row": ("equals", "RVM-01")}}),
        _app("A9.22", "config/mission/mission_scenario_v1.json", A922_CONFIG_COMMIT, ['"altitude_domain_km"'],
             "frozen mission scenario: altitude domain consumed from the snapshot field mission_domain.altitude_km",
             {"node": "/inputs/altitude_domain_km/source",
              "checks": {"snapshot_field": ("equals", "mission_domain.altitude_km")}})],
    ("A9.22", "G6_IC_HALL_PREFERRED"): [
        _app("A9.22", "abep_sim/system.py", A922_PHASE_B_COMMIT,
             ['RAW_CLOSURE_SCHEMA_VERSION = "raw_closure_v2"', "def physics_closure"],
             "raw physics closure (schema increment raw_closure_v2): no IC metric, preference flag or compliance "
             "classification"),
        _app("A9.22", "abep_sim/assessment/closure_checks.py", A922_PHASE_B_COMMIT,
             ["FORBIDDEN_RAW_KEYS", '"hall_preferred"', "def legacy_merge"],
             "assessment layer: IC metrics, hall_preferred, RFP / compliance classifications; legacy merge keeps "
             "the pre-split evaluate() dict for existing tools")],
    ("A9.22", "G7_DEAD_LOGIC"): [
        _app("A9.22", "abep_sim/transient.py", A922_PHASE_B_COMMIT,
             ['always-true "ignition_req_met" flag was removed'], "ignition_req_met '... or True' removed"),
        _app("A9.22", "tests/test_raw_assessment_split.py", A922_PHASE_B_COMMIT,
             ["def test_dead_logic_removed", 'not hasattr(sizing, "RFP")', '"duty_cycle" not in'],
             "structural test: Budgets.duty_cycle, the unused RFP import in sizing and the always-true flag are "
             "gone; evaluate() identical to the base-commit fixture")],
    ("A9.22", "G8_BUS_BOUNDARY"): [
        _app("A9.22", "docs/architecture_comparison/power_boundary_a9_v2/bus_power_boundary_a9_v2.json",
             A922_G8_STAGE1_COMMIT, ['"boundary_version": "bus_power_boundary_a9_v2"', '"configurations": ['],
             "bus_power_boundary_a9_v2: hall_icp_neutralizer only; hall_c1_reference ground-reference / test "
             "metadata, not a flight bus configuration (v1 immutable)",
             {"node": "/ground_reference_test_metadata/hall_c1_reference",
              "checks": {"role": ("equals", "GROUND_ONLY_LAB_REFERENCE"),
                         "flight_bus_configuration": ("equals", False)}}),
        _app("A9.22", "abep_sim/bus_boundary_a9_v2.py", A922_G8_STAGE1_COMMIT,
             ['BOUNDARY_VERSION = "bus_power_boundary_a9_v2"'], "v2 boundary module (v1 runs unchanged)"),
        _app("A9.22", "docs/architecture_comparison/power_boundary_a9_v2/CONSUMER_INVENTORY.json",
             A922_G8_STAGE1_COMMIT, ['"LIVE_REPOINT"'], "consumer inventory listed before anything changed"),
        _app("A9.22", "docs/architecture_comparison/power_boundary_a9_v2/STAGE2_MIGRATION.json",
             A922_G8_STAGE2_COMMIT, ['"verdict": "NO_PHYSICS_RESULT_CHANGED', '"v1_family_byte_identical"'],
             "one controlled migration: LIVE_REPOINT consumers re-pointed with pins together; v1 byte-identical; "
             "no physics result changed")],
    ("A9.22", "G9_F1_OUTPUT"): [
        _app("A9.22", "docs/evidence_archives/f1_intake/F1_INTAKE_SYNTHESIS_v1_405296e.manifest.json",
             A922_G9_COMMIT, ['"schema": "evidence_archive_manifest_v1"', '"generating_commit"', '"input_manifest"'],
             "deterministic F1 evidence archive manifest (archive sha256 / size, generating commit, architecture / "
             "design-state-set / input-manifest hashes, command, timestamp, per-file sha256, classification)",
             {"node": "/storage/preferred", "checks": {"kind": ("startswith", "GitHub Release asset"),
                                                       "status": ("equals", "PENDING_OWNER_UPLOAD")}}),
        _app("A9.22", "docs/design_synthesis/f1_intake/f1_core_view.py", A922_G9_COMMIT,
             ['CORE_SCHEMA = "f1_intake_synthesis_v1_core"', "def expand_core"],
             "compact F1 core view for consumers (lossless)"),
        _app("A9.22", "scripts/evidence/f1_archive.py", A922_G9_COMMIT, ["def build_manifest", "def verify"],
             "archive builder / byte-for-byte verifier (original kept until hash-verified)")],
}
LATER_STATUS = {
    ("A9.18", "PERF_RERUN"): ("BLOCKED", "owner-machine action after the step-3 merge (nothing to run now): the identical "
                              "dedicated procedure on the idle owner machine; not runnable in this environment"),
    ("A9.21", "PERF_RERUN"): ("BLOCKED", "owner-machine action: the owner reruns the dedicated baseline on the exact "
                              "commit SHA supplied to them, into a new folder (previous baseline unchanged); the SHA is "
                              "sent after the merge; not runnable in this environment"),
    ("A9.21", "BID_CLOSE"): ("NOT_APPLICABLE_TO_ARTIFACTS", "an operational submission deadline (DefProc tender "
                             "2026_DRDO_788433_1), not a requirement of the registered RFP (not in the PDF); recorded in "
                             "state v5 WEB-ACC-2"),
    ("A9.21", "RFQ_DISPATCH"): ("NOT_APPLICABLE_TO_ARTIFACTS", "the quotation packages exist in the repository "
                                "(docs/procurement/rfq_a9_v3); dispatch is an owner / procurement act"),
}
LATER_RESIDUAL = {
    ("A9.22", "G2_C_DRAG_RFP"): [
        ("LATER_SEPARATE_OWNER_APPROVAL", "Option 2 (generate all designs, apply drag <= 25 mN only in the "
         "assessment layer) is recorded as a later semantic / model-pipeline change; it changes the F1-F8 Pareto "
         "populations and robustness counts and needs a separate owner approval (not applied)", "owner")],
    ("A9.22", "G9_F1_OUTPUT"): [
        ("PENDING_OWNER_UPLOAD", "the hash-verified F1 archive F1_INTAKE_SYNTHESIS_v1_405296e.tar.zst is uploaded by "
         "the owner as the GitHub Release asset (tag evidence-f1-intake-synthesis-v1-405296e); the original full F1 "
         "file is removed from the working tree only after the re-downloaded asset is hash-verified byte for byte",
         "owner (GitHub Release on ppusapati/abep)")],
    ("A9.22", "G3_REQUIREMENTS_SNAPSHOT"): [
        ("PENDING_EVIDENCE", "compliance of the frozen rows: freezing the requirement basis changes no RVM status; "
         "every row stays as evaluated until determining evidence exists", "hardware programme / RVM")],
    ("A9.17", "ORBIT"): [("PENDING_EVIDENCE", "inclination / LTAN from DRDO / spacecraft ICD / PDR mission definition, "
                          "then a new dataset version", "official mission ICD (owner)")],
    ("A9.17", "PERF"): [("BLOCKED", "superseded as the admission baseline by the A9.18 PERF_RERUN (after the step-3 "
                         "merge); the 2026-10-01 dedicated run is historical for the earlier code state",
                         "owner machine (A9.18 PERF_RERUN)")],
    ("A9.18", "GOLDEN"): [("BLOCKED", "docs/traceability/rtm_v1.json / RTM.md still cite abep_sim/data/golden_v1.json "
                           "(written when golden_v1 was canonical). The RTM is a pinned historical record: the RVM "
                           "pins both files by sha256 under HISTORICAL_KEYS and M16 v1 / v2 record the rtm_v1.json "
                           "sha256, and M16 v2 is pinned by the immutable M16 v3 builder; re-pointing would break that "
                           "immutable chain. A re-pointed RTM needs a new RTM version (owner call)",
                           "docs/traceability/ (rtm_v2, not started)")],
    ("A9.18", "PERF_RERUN"): [("BLOCKED", "dedicated baseline rerun after the step-3 merge, before any Rust performance "
                               "admission", "owner machine")],
    ("A9.21", "PERF_RERUN"): [("BLOCKED", "exact commit SHA to the owner after the merge; rerun into a new folder",
                               "owner machine")],
    ("A9.21", "AL08"): [("PENDING_EVIDENCE", "quotations split into tank, regulator, valves, plumbing, mounting/thermal "
                         "and any C1-specific branch, then the formal AL-08 re-base", "supplier quotations (owner / "
                         "procurement)"),
],
    ("A9.21", "ICP_GATE"): [("PENDING_OWNER_ACCEPTANCE", "numerical GO / NO-GO criteria: not approved; the recorder "
                             "proposal text (RP-A919-01 (a) - (c)) is preserved for owner review", "owner")],
    ("A9.21", "HW_PROGRAMME"): [("PENDING_OWNER_ACCEPTANCE", "recorder readings RR-01 (Ar reference keeps its "
                                 "per-stage freeze points; 'close before it starts' applied to the two registered "
                                 "campaigns), RR-02 (C1-REF after H1-S7.2) and RR-03 (step ids) recorded in the programme "
                                 "record for the owner to accept or reverse", "owner"),
                                ("PENDING_EVIDENCE", "the hardware runs themselves (FEMM, H-1 + C1 reference "
                                 "characterization, ICP campaigns, P2 map, coupled thermal, measured thrust / feed map)",
                                 "hardware programme")],
    ("A9.21", "EXTERNAL_INPUTS"): [("PENDING_EVIDENCE", "AOCS pointing envelope, inclination / LTAN, host-spacecraft drag "
                                    "ICD", "DRDO / spacecraft ICD / PDR mission definition")],
    ("A9.21", "RFQ_DISPATCH"): [("BLOCKED", "dispatch of the quotation packages", "owner / procurement")],
}

INTEGRATION_COMMITS = {"repin": "5acdcde8be7d41cfb0d6c26b1ad7cb899d279871",
                       "records": "d681230d79e98de1f68085310950086e5e18048c"}
# A9.16 repair lane (review findings F1-F11, COR-01..07): the commit that applied the decisions below. Every
# application is verified at build time like a lane result (the question id must occur in the artifact).
REPAIR_COMMIT = "1d515542e268dc042c9e48a4b1e496de4891f6e5"
REPAIR = [
    # (question id, artifact, what) - F1 / F5
    ("ICPQ-10", "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
     "F1: P2 records ICPQ-10 OWNER_DECIDED (A9.12 S5.1 alternative A); alternative B only as rejected history; RC-HEAT "
     "references p3_a9_16_rules.icp43_total_module_bound and refuses any other heat_load_option"),
    ("OQ-A910-06", "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
     "F5: P2 output OQ-A910-06 OWNER_DECIDED (A9.12 S5.8), P2 envelope consumed by p3_a9_16_rules.rf_thermal_basis"),
    ("OQ-A910-06", "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json",
     "F5: open_register_status OQ-A910-06 OWNER_DECIDED (A9.12 S5.8)"),
    # F2
    ("P3Q-01", "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
     "F2: P1-M-30 REQUIRED Langmuir probe (matched diagnostic runs, calorimetry primary); capacity records exclude an "
     "undeclared / unevidenced probe; XL-18 / XL-25 re-stated"),
    ("P3Q-01", "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json",
     "F2: XL-18 re-stated on the P3 side (P3-IF-N02)"),
    ("P3Q-01", "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
     "F2: XL-25 re-stated on the P4 side (ID-06)"),
    # F3
    ("OD5", "docs/requirements/rvm_a9/rvm_a9_v1.json",
     "F3: RVM-14 ICP-first sequence limited by registered dwell / thermal limits only; 120 s / 360 s kept for the "
     "C1-selected variant's Xe booking"),
    ("XA9Q-02", "docs/requirements/rvm_a9/rvm_a9_v1.json", "F3: 120 s / 360 s scoped to the C1 variant"),
    # F4
    ("OQ-RFQV2-10", "docs/procurement/rfq_a9_v3/rfq_a9_v3.json",
     "F4: RFQ3-H1FAB sent against the P9e configuration-controlled P1 engineering drawing set; LOCK-1 release kept for "
     "the flight H-1 only (recorder reading for the owner to confirm)"),
    # F6 / F11
    ("MPQ-01", "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json",
     "F6: P-FL-C1 a configuration-scope zero (no C1 in hall_icp_neutralizer), not an owner Xe exclusion; XV2-02 and the "
     "C1 sensitivity labelled A5 design-target placeholders"),
    ("XA9Q-05", "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json",
     "F11: ICP-feed 'contingency' label traced to A9.1 HIQ-06; whether A9.15 changes it is open owner question XV3Q-01"),
    # F9
    ("P1Q-19", "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
     "F9: the rejected alternative is NOT_OWNER_SELECTED_INFORMATIONAL (no margin, no condition_met); docstrings "
     "follow the owner choice"),
    # F10
    ("OQ-A907-01", "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json",
     "F10: C-S4 keeper ignition <= 3 dwells (1 + 2 retries) x 120 s = 360 s maximum booking"),
    ("XA9Q-02", "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json", "F10: as above"),
    # F8
    ("OD5", "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json",
     "F8: AFC-SY-CTL-01 sequence OWNER_DECIDED, dwell / thermal limits PENDING_REGISTRATION"),
    ("XA9Q-07", "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json",
     "F8: Xe rows re-pointed to xe_accounting_a9_v3 / mass_power_a9_v3 / state v5 (v2 / v4 sources marked history)"),
    # COR-06 / COR-07
    ("P4-OQ-01", "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
     "COR-06: CR-01 admits T_validated_continuous only with a referenced stage record (id + sha256) classified by "
     "validation_stage_record; a bare declaration is INCOMPLETE_EVIDENCE"),
    ("P2Q-01", "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
     "COR-07: method_agreement needs ZM-B valid = True at the same operating point / configuration"),
    ("P2Q-03", "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json", "COR-07: as above"),
]
REPAIR_FIXES = [
    {"id": "COR-01", "what": "immutable state-v4 builder reproduces again: P1 / P2 keep their as-raised "
     "open_owner_questions (current status in owner_question_status_current / answered_owner_questions + "
     "owner_questions_open_now), P1 derived_resolutions keep the as-raised disposition (owner_decision beside it), "
     "P4 / RVM keep the as-raised status (status_current beside it), P3 v1 is the A9.6 package"},
    {"id": "COR-02", "what": "immutable RFQ v2 builder reproduces again: P1-IT-36 and P1-M-30 keep the read-back "
     "status / quantity text (status_a9_16 / quantity_a9_16 govern)"},
    {"id": "COR-05", "what": "build_p3_coupled_thermal.py and its v1 outputs restored byte-identical (F0-profiled "
     "source pinned through the parity pre-registration); every A9.16 P3 change moved to build_p3_coupled_thermal_v2.py "
     "-> p3_coupled_thermal_v2.json / P3_COUPLED_THERMAL_V2.md, which the current-state consumers read"},
    {"id": "COR-03", "what": "F4 regenerated (build_f4_plenum.py, build CPU 102 s): only its pin of the current H-1 "
     "freeze candidate changed; --check and tests/test_design_f4_plenum.py::test_pins_hold pass"},
    {"id": "COR-04", "what": "F7 / F8 NOT regenerated: its builder exceeds the 2-minute command limit (BLOCKED; pins "
     "to F6 / H-1 / F4 stay stale until a run without that limit)"},
]

# ------------------------------------------------------------------------------------------------ lane results
LANES = {
    "P1": ("b1bac8dc5df0a03e55954e0f0b26bf27bdcd86a4", "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
           ["P1Q-04", "P1Q-09", "P1Q-11", "P1Q-18", "P1Q-20", "P1-IT-52", "P1-IT-55", "OQ-RFQV2-06", "OQ-RFQV2-08",
            "P1Q-02", "P1Q-03", "P1Q-05", "P1Q-06", "P1Q-07", "P1Q-08", "P1Q-19", "P1Q-24", "OQ-RFQV2-09", "P1Q-01",
            "P1Q-17", "P1Q-12", "OD5", "ICPQ-08", "F6-OQ-03"]),
    "P2": ("3ff91954875e69f2baf9ba41cca546c657d6260d",
           "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
           ["P2Q-01", "P2Q-03", "P2Q-04", "P2Q-07", "P2Q-08", "P2Q-09", "P1Q-24", "P2Q-02", "ICPQ-11", "P2Q-10",
            "P2Q-06", "F6-OQ-02"]),
    "P3": ("c00f9b5c424feda2c653c87b3eb1b7d9d3a51009",
           "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json",
           ["P3Q-01", "ICPQ-10", "OQ-A907-03", "OQ-A907-05", "OQ-A907-06", "OQ-A907-08", "OQ-A907-09", "OQ-A907-10",
            "OQ-A910-06", "P3Q-02", "ICPQ-03", "ICPQ-09"]),
    "P4": ("673c058c4dd0a52633470e1c4593ab41f99f7665",
           "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
           ["P4-OQ-01", "P4-OQ-02", "P4-OQ-03", "P4-OQ-04", "P4-OQ-05", "OQ-A907-05", "F2-OQ-04"]),
    "RFQ": ("f68b9999ebc89c41ab051bfaebf03c04fc58cc78", "docs/procurement/rfq_a9_v3/rfq_a9_v3.json",
            ["P2Q-02", "OQ-RFQV2-01", "OQ-RFQV2-02", "OQ-RFQV2-03", "OQ-RFQV2-04", "OQ-RFQV2-05", "OQ-RFQV2-06",
             "OQ-RFQV2-08", "P1-IT-55", "OQ-RFQV2-09", "OQ-RFQV2-10", "P2Q-07", "OQ-RFQ-01", "OQ-RFQ-03", "OQ-RFQ-04",
             "OQ-RFQ-08", "OQ-RFQ-09", "XA9Q-06", "XA9Q-01", "OQ-A907-04", "XA9Q-07", "XA9Q-05", "P1Q-09", "P3Q-01",
             "P1Q-17", "MQ-05"]),
    "MASS_POWER_V3": ("d008ac31daa11b6d0fcfe4ad78f9587e359bced3", "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json",
                      ["MQ-01", "MQ-02", "MQ-03", "MQ-04", "MQ-05", "MQ-06", "MQ-07", "MQ-09", "MQ-10", "MPQ-01",
                       "MPQ-02", "OQ-A907-07", "OQ-A910-01", "OQ-A910-03", "OQ-A910-05", "XA9Q-07"]),
    "XE_V3": ("d008ac31daa11b6d0fcfe4ad78f9587e359bced3", "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json",
              ["XA9Q-07", "XV2Q-01", "XA9Q-02", "OQ-A907-01", "XA9Q-03", "XA9Q-04", "XA9Q-06", "XA9Q-05", "XA9Q-01",
               "MQ-09", "OQ-A910-01", "OD6", "OQ-A907-07", "MPQ-01"]),
}
# A9.15 reviews by lanes (no 'Xe contingency-only for C1' wording to amend): NOT_APPLICABLE applications
A915_REVIEWED_NA = {"P1": "P1 is the Ar engineering step; no Xe-contingency wording; G-REUSE unchanged",
                    "P2": "no Xe-contingency wording; G-REUSE / G-XE ICP gas modes unchanged",
                    "P3": "no Xe-contingency wording and no Xe heat term",
                    "P4": "no Xe-contingency wording; Xe+ stays a sputter species because Xe is RFP-required"}
A915_APPLIED = {"RFQ": "RFQ3-GAS-N03 / RFQ3-GAS-N04, NIR-07: system Xe capability for both configurations, C1 Xe "
                       "lines only for a selected C1 needing Xe, ICP getter an engineering / vendor requirement",
                "MASS_POWER_V3": "propellant_policy; C1 Xe branch neither assumed nor excluded (AL-08)",
                "XE_V3": "propellant_policy; RA-FUNC APPLIES; Xe-free reading retired; XV2Q-01 NOT_APPLICABLE"}

# integration artifacts (this lane) and the key of their owner-answer rows
INTEGRATION = {
    "docs/budgets/owner_decisions/owner_questions_state_v5.json": None,
    "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json": "a9_16_owner_answers_applied",
    "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json": "a9_16_owner_answers_applied",
    "docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json": "owner_answers_applied",
    "docs/requirements/rvm_a9/rvm_a9_v1.json": "a9_16_owner_answers_applied",
    "docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json": "a9_16_owner_answers_applied",
}

# A9.13 decisions whose application changes design-synthesis / optimizer / production-path code (step 3)
STEP3 = {
    "F1Q-02": "F1 intake synthesis: budgeting-assumption labels, sourced structure before LOCK-1",
    "F1Q-03": "F1 / intake-surface v2 domain over the registered AOCS pointing envelope",
    "F2-OQ-01": "F2 filter stage: baseline protection functions and pre-registered acceptance fields",
    "F2-OQ-02": "F2 concept list: catalytic O->O2 element as a separate research variant",
    "F2-OQ-03": "F2 / F7 contexts: FC-00 'none' as a reference bound only",
    "OQ-F3-02": "F3 compressor geometry: explicit hub ratio / blade span",
    "OQ-F3-03": "F3: transitional-regime model in parallel; NOT_EVALUATED_OUT_OF_DOMAIN above 0.1 Pa",
    "OQ-F3-04": "F3 search: Al / CFRP re-admitted only through the S2.3 strength-basis gate",
    "OQ-F4-01": "F4 plenum control: scheduled setpoint baseline, fixed setpoint fallback",
    "OQ-F4-02": "F4: higher-pressure compression as the primary direction",
    "OQ-F4-04": "F4 / F7: flow-gap levers in the owner order (no requirement relaxation)",
    "OQ-F4-05": "orbit-resolved frozen atmosphere dataset (rule-1 versioned build) and its use in F4 / F7",
    # A9.16 repair F7: only a state-v5 row / F9 annotation exists; the F4 / F7-F8 records that hold these decisions are
    # not rebuilt (CPU limit) - not APPLIED
    "OQ-F4-03": "F4 transient metrics accepted provisionally: annotation of the F4 record (F-lane regeneration)",
    "OQ-F78-02": "F7 / F8: all admitted scenarios carried: annotation of the F7 / F8 records (F-lane regeneration)",
    "OQ-F78-01": "F7 / F8: HC-08 hard statewise T - D >= 0",
    "OQ-F78-03": "F7 / F8: ripple as a hard feed-quality constraint; Pareto (no weighted scalar)",
    "OQ-F78-04": "F7 / F8: REFERENCE/PARAMETRIC sourced spacecraft geometry for interim drag studies",
    "UPSTREAM_ICD-Q1": "filter as a separate production-path element between IF-A1 and IF-A2",
    "F9-OQ-02": "F4 / F7: AG-12 feed-state constraint in the upstream evaluation (F9-ID-09)",
}

# residual items (status, what, where)
RESIDUAL = {
    "OD3": [("BLOCKED", "design-layer consumers of the A9.14 S9.8 design-state set: abep_sim/design/intake_synthesis.py ENVELOPE_STATES (h200_f150 + four alt x F10.7 corners of the orbit-averaged atmosphere_msis21_v1) and abep_sim/design/architecture_optimizer.py STATES = isy.ENVELOPE_STATES (F1-F8; HC-09 'every orbit state', AG-12 / AG-13 statewise constraints) still evaluate five hand-picked orbit-averaged states, not atmosphere_msis21_orbit_v1_design_states_v2; the RVM cites the built set (RVM-01 design_states REGISTERED_NOT_YET_CONSUMED) - A9.16 repair RVF-03", "abep_sim/design/** (design lane)")],
    "OQ-F4-05": [("PENDING_FINALIZE_DESIGN_REGEN", F_REGEN, F_REGEN_WHERE),
                 ("BLOCKED", "design-layer consumers of the A9.14 S9.8 design-state set: abep_sim/design/intake_synthesis.py ENVELOPE_STATES (h200_f150 + four alt x F10.7 corners of the orbit-averaged atmosphere_msis21_v1) and abep_sim/design/architecture_optimizer.py STATES = isy.ENVELOPE_STATES (F1-F8; HC-09 'every orbit state', AG-12 / AG-13 statewise constraints) still evaluate five hand-picked orbit-averaged states, not atmosphere_msis21_orbit_v1_design_states_v2; the RVM cites the built set (RVM-01 design_states REGISTERED_NOT_YET_CONSUMED) - A9.16 repair RVF-03", "abep_sim/design/** (design lane)")],
    "OQ-A907-03": [("BLOCKED", "A9-07 uncoupled thermal rerun bounding corners", "docs/hardware/h2_a9_revisions/** "
                    "(outside the allowed paths)")],
    "OQ-A907-05": [("BLOCKED", "provisional BN / ceramic-wire limits in the A9-07 revisions",
                    "docs/hardware/h2_a9_revisions/** (outside the allowed paths)")],
    "OQ-A907-06": [("BLOCKED", "mount-heat levers (50 W governing) in the A9-07 revisions",
                    "docs/hardware/h2_a9_revisions/** (outside the allowed paths)")],
    "OQ-A907-08": [("BLOCKED", "coating limit in the A9-07 revisions", "docs/hardware/h2_a9_revisions/**")],
    "OQ-A907-09": [("BLOCKED", "environmental margin in the A9-07 revisions", "docs/hardware/h2_a9_revisions/**")],
    "OQ-A907-10": [("BLOCKED", "search allowance / SEARCH_SENSITIVE flag in the A9-07 revisions",
                    "docs/hardware/h2_a9_revisions/**")],
    "ICPQ-10": [("PENDING_EVIDENCE", "Q_ICP,bound value needs the registered P_fwd,max (complete P2 envelope) and "
                 "the registered H-1 P_d,max (form decided; RC-HEAT TBD_AFTER_EVIDENCE)",
                 "docs/experiments/hall_icp/p2_impedance_map/, p3_coupled_thermal/")],
    "F5-OQ-02": [("PENDING_EVIDENCE", "the engineering channel point itself is not yet selected: H1F-CH-11 "
                  "NOT_SELECTED_PENDING_FEMM (the non-performance selection rule and the ENGINEERING_FREEZE_CANDIDATE "
                  "label are recorded)", "docs/hardware/h1_freeze_candidate/ (after the authorised FEMM analysis "
                                         "points, F5-OQ-01)")],
    "P4-OQ-02": [("BLOCKED", "XL-27 pair text 'coupon shortlist TBD_OWNER P4 IT-17' must stay identical with RFQ v2 "
                  "IFD-17", "docs/procurement/rfq_a9_v2/ (immutable v2; outside the allowed paths)")],
    "F2-OQ-04": [("PENDING_FINALIZE_DESIGN_REGEN", "F2 lane F2-IF-08 status 'TBD_OWNER (F2-OQ-04)' stale until the F2 "
                  "record is regenerated from the step-3 filter_stage code", "docs/design_synthesis/f2_filter/")],
    "OQ-F4-03": [("PENDING_FINALIZE_DESIGN_REGEN", "F4 record annotation (provisional metric acceptance)", F_REGEN_WHERE)],
    "OQ-F78-02": [("PENDING_FINALIZE_DESIGN_REGEN", "F7 / F8 record annotation (all admitted scenarios)",
                   F_REGEN_WHERE)],
    "OQ-F78-04": [("PENDING_FINALIZE_DESIGN_REGEN", "F7 / F8 not regenerated in the repair lane (COR-04): its pins to "
                   "F6 / H-1 / F4 are stale at this matrix's base", F_REGEN_WHERE)],
    "MQ-06": [("OPEN_OWNER_QUESTION", "controls-line allocation after the split: MPV3Q-01 (TBD_OWNER in state v5)",
               "docs/budgets/mass_power_a9_v3/")],
    # OQ-A907-07 / MPQ-01: the 'wait for C1 selection' residuals are gone - A9.19 removes the C1 flight variant
    # (SUPERSEDED_BY_LATER_DECISION; see the A9.19 entry)
    # F9-OQ-03 / OD12: the PENDING_OWNER_ACCEPTANCE residuals are resolved by A9.22 G3 (RESOLVED_RESIDUAL_AG15)
    "F0-OQ-02": [("BLOCKED", "the 2026-10-01 dedicated run is historical for the earlier code state: A9.18 PERF_RERUN "
                  "(identical procedure after the step-3 merge, idle owner machine) is the Rust-admission baseline",
                  "owner machine (A9.18 PERF_RERUN)")],
    # the BLOCKED re-derivation residual is APPLIED by M16 v5 (RESOLVED_RESIDUAL; structural record check in CODE_APPS)
    "M16-V3-Q-01": [("PENDING_EVIDENCE", "named persons from the project staffing ledger (none in the repository; none "
                     "fabricated)", "staffing ledger (owner)")],
}
NOT_APPLICABLE = {
    "OQ-A910-02": "the producing stage and decision quantity are assigned at LOCK-1 from the frozen A9-01 stage map and "
                  "the decision-quantity consumer table; no assignment is inferred now to eliminate a TBD (registered "
                  "in state v5)",
}
SPECIAL = {
    # A9.16 repair RVF-03: the set is built (A9.17) but no design consumer evaluates it yet
    "OD3": ("PARTIAL", "design-state set v2 built from the frozen orbit-resolved dataset (A9.17) and cited by the RVM, "
                       "but the design-layer statewise evaluators still use the five orbit-averaged ENVELOPE_STATES "
                       "(no consumer of the set; residual BLOCKED)"),
    "F5-OQ-02": ("PARTIAL", "selection rule recorded (non-performance criteria, ENGINEERING_FREEZE_CANDIDATE); the "
                 "engineering channel point is not yet selected (H1F-CH-11 NOT_SELECTED_PENDING_FEMM) - A9.16 repair F7"),
}
RULES = [
    {"id": "R-RUST-OQ-01", "decision": None, "rule": "Python is authoritative for frozen and score-bearing outputs: "
     "frozen datasets, golden / reference rebuilds and score-bearing evidence are produced or independently reproduced "
     "by the Python reference; an admitted Rust kernel may accelerate exploration, CI parity and non-authoritative runs",
     "application": "abep_sim/design/tpmc_backend.py has no frozen-data or score-bearing path (default backend python; "
                    "not wired into the intake-surface build, goldens or scoring), so no refusal code is added: editing "
                    "the wrapper would also change the parity-report build provenance and de-admit the kernels "
                    "(RUST-OQ-02). Guarded by tests/test_decision_application_a9_16.py::"
                    "test_frozen_and_score_bearing_paths_never_use_rust",
     "status": "APPLIED"},
    {"id": "R-RFP", "decision": None, "rule": "the official RFP is registered by hash in the public repository (A9.17 "
     "RFP; docs/requirements/rfp_official/rfp_registration_v1.json, PDF in the controlled evidence store) and the RVM is "
     "re-based on its clauses; the step-1 records keep rfp_citation_status OWNER_STATED_PENDING_RFP_REGISTRATION as the "
     "history of the state in which they were applied (step-1 rule: " + L.RFP_PENDING_NOTE + "); the owner closed "
     "AG-15 (A9.22 G3): requirement_frozen = true on the RFP_CLAUSE rows, RFP-derived requirements snapshot FROZEN "
     "(basis only, no compliance claim)", "status": "APPLIED",
     "application": "state v5 rfp_registration_now + a9_22_g3; F9-OQ-03 'ag_15' (registration + re-base + owner "
                    "acceptance APPLIED); step-1 rows, F9 / RVM records carry rfp_citation_status as history"},
    {"id": "R-A919", "decision": "A9.19 / A9.20", "rule": "one flight configuration hall_icp_neutralizer: one Hall "
     "accelerator + one RF/ICP electron-source / neutralizer for air and Xe, two supply modes (ambient atmospheric "
     "primary, Xe contingency / emergency), no conventional hollow cathode; C1 = GROUND_ONLY_LAB_REFERENCE; "
     "hall_c1_reference retired as a flight configuration (labelled history / ground reference only)",
     "status": "APPLIED", "application": "A9.19 / A9.20 entries below (RVM, budgets v3, design layer, F9, state v5, "
                                         "M16 v4); earlier entries they amend carry amended_by_later"},
    {"id": "R-A915", "decision": None, "rule": L.a915_governing_statement(), "status": "APPLIED",
     "application": "A9.15 governs every 'Xe contingency-only for C1' reading; the A9.1 ICP gas-mode baseline (G-REUSE "
                    "primary, G-XE a declared ICP-feed variant) is unchanged"},
]


EXTRA_APPS = {
    "RUST-OQ-01": [{"lane": "INTEGRATION", "artifact": "tests/test_decision_application_a9_16.py",
                    "commit": INTEGRATION_COMMITS["records"], "status": "APPLIED",
                    "record_locations": ["test_frozen_and_score_bearing_paths_never_use_rust"],
                    "what": "rule R-RUST-OQ-01 recorded here; guard test: no frozen / golden / score-bearing path imports "
                            "tpmc_backend or abep_core; tpmc_backend default backend python (no frozen-data path exists "
                            "in tpmc_backend, so no refusal code is added)"}],
}


def _qid_re(qid):
    return re.compile(r"(?<![A-Za-z0-9-])" + re.escape(qid) + r"(?![0-9A-Za-z])")


def _locations(doc, qid, limit=4):
    pat = _qid_re(qid)
    out = []

    def walk(o, p):
        if len(out) >= limit:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{p}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{p}/{i}")
        elif isinstance(o, str) and pat.search(o):
            out.append(p)
    walk(doc, "")
    return out


def repair_applications():
    apps = {}
    for qid, art, what in REPAIR:
        doc = json.loads((ROOT / art).read_text(encoding="utf-8"))
        locs = _locations(doc, qid)
        if not locs:
            raise SystemExit(f"REPAIR: question id {qid} not found in {art} (repair application not verifiable)")
        apps.setdefault(qid, []).append({"lane": "REPAIR", "artifact": art, "commit": REPAIR_COMMIT,
                                         "status": "APPLIED", "record_locations": locs, "what": what})
    return apps


def lane_applications():
    apps = {}
    for lane, (commit, art, qids) in LANES.items():
        doc = json.loads((ROOT / art).read_text(encoding="utf-8"))
        for q in qids:
            locs = _locations(doc, q)
            if not locs:
                raise SystemExit(f"{lane}: question id {q} not found in {art} (lane result not verifiable)")
            apps.setdefault(q, []).append({"lane": lane, "artifact": art, "commit": commit, "status": "APPLIED",
                                           "record_locations": locs})
    return apps


def integration_applications():
    apps, a915 = {}, []
    commit = INTEGRATION_COMMITS["records"]
    for art, key in INTEGRATION.items():
        doc = json.loads((ROOT / art).read_text(encoding="utf-8"))
        if key is None:     # state v5: one registered row per answered question
            for i, r in enumerate(doc["rows"]):
                if r.get("answer_decision"):
                    apps.setdefault(r["id"], []).append({
                        "lane": "INTEGRATION", "artifact": art, "commit": commit, "status": "APPLIED",
                        "record_locations": [f"/rows/{i}"], "what": f"state v5 row {r['status']}"})
            continue
        for i, row in enumerate(doc[key]):
            if "question_id" not in row:
                continue
            if row["decision"] == "A9.15":
                a915.append({"lane": "INTEGRATION", "artifact": art, "commit": commit,
                             "status": "NOT_APPLICABLE_TO_ARTIFACTS" if row["how_applied"].startswith("reviewed")
                             else "APPLIED", "record_locations": [f"/{key}/{i}"], "what": row["how_applied"]})
                continue
            apps.setdefault(row["question_id"], []).append({
                "lane": "INTEGRATION", "artifact": art, "commit": commit, "status": "APPLIED",
                "record_locations": [f"/{key}/{i}"] + [r for r in row["record_ids"]][:4], "what": row["how_applied"]})
    return apps, a915


def _verify_app(spec, qid):
    """Fail closed: every locator token must occur verbatim in the artifact text."""
    path = ROOT / spec["artifact"]
    if not path.exists():
        raise SystemExit(f"{qid}: application artifact {spec['artifact']} missing")
    text = path.read_text(encoding="utf-8")
    missing = [t for t in spec["tokens"] if t not in text]
    if missing:
        raise SystemExit(f"{qid}: tokens {missing} not found in {spec['artifact']} (application not verifiable)")
    out = {"lane": spec["lane"], "artifact": spec["artifact"], "commit": spec["commit"], "status": "APPLIED",
           "record_locations": list(spec["tokens"]), "what": spec["what"]}
    if spec.get("record"):
        out["record_pointer"] = _verify_record(json.loads(text), spec["record"], qid, spec["artifact"])
    if spec.get("pin"):
        out["pin_pointer"] = _verify_pin(json.loads(text), spec["pin"], qid, spec["artifact"])
    return out


def _verify_pin(doc, pin, qid, artifact):
    """Fail closed: the value at the JSON pointer must equal the sha256 of the pinned repository file as it is now."""
    import hashlib
    pointer, rel = pin
    node = doc
    for part in pointer.strip("/").split("/"):
        node = node.get(part) if isinstance(node, dict) else None
        if node is None:
            raise SystemExit(f"{qid}: {artifact}{pointer} missing (pin not verifiable)")
    want = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    if node != want:
        raise SystemExit(f"{qid}: {artifact}{pointer} = {node!r} is not the current sha256 of {rel}")
    return f"{pointer} = sha256({rel})"


def _verify_record(doc, rec, qid, artifact):
    """Fail closed: exactly one record of the JSON list at rec['list'] matches rec['match'] and every field check holds
    (('equals', v) or ('startswith', prefix)). Returns the JSON pointer of the record."""
    if "node" in rec:      # (A9.22) a JSON object at a pointer, field checks on it (no list / match)
        rec = {"list": rec["node"].rsplit("/", 1)[0] or "/", "_obj": rec["node"].rsplit("/", 1)[1],
               "checks": rec["checks"]}
    node = doc
    for part in rec["list"].strip("/").split("/") if rec["list"].strip("/") else ():
        node = node[int(part)] if isinstance(node, list) else node.get(part) if isinstance(node, dict) else None
        if node is None:
            raise SystemExit(f"{qid}: {artifact}{rec['list']} missing (application not verifiable)")
    if "_obj" in rec:
        x = node.get(rec["_obj"]) if isinstance(node, dict) else None
        ptr = f"{rec['list'].rstrip('/')}/{rec['_obj']}"
        if not isinstance(x, dict):
            raise SystemExit(f"{qid}: {artifact}{ptr} missing or not an object (application not verifiable)")
        for field, (op, want) in rec["checks"].items():
            got = x.get(field)
            if op not in ("equals", "startswith"):
                raise SystemExit(f"{qid}: unknown record check op {op!r} for {field}")
            ok = got == want if op == "equals" else isinstance(got, str) and got.startswith(want)
            if not ok:
                raise SystemExit(f"{qid}: {artifact}{ptr}.{field} = {got!r} fails {op} {want!r}")
        return ptr
    key, val = rec["match"]
    hits = [i for i, x in enumerate(node) if isinstance(x, dict) and x.get(key) == val]
    if len(hits) != 1:
        raise SystemExit(f"{qid}: {artifact}{rec['list']}: {key}={val!r} found {len(hits)} times")
    x = node[hits[0]]
    for field, (op, want) in rec["checks"].items():
        got = x.get(field)
        if op not in ("equals", "startswith"):
            raise SystemExit(f"{qid}: unknown record check op {op!r} for {field}")
        ok = got == want if op == "equals" else isinstance(got, str) and got.startswith(want)
        if not ok:
            raise SystemExit(f"{qid}: {artifact}{rec['list']}/{hits[0]}.{field} = {got!r} fails {op} {want!r}")
    return f"{rec['list']}/{hits[0]} ({key}={val})"


def code_applications():
    apps = {q: [_verify_app(s, q) for s in specs] for q, specs in CODE_APPS.items()}
    for q, (_, specs) in STEP3_PARTIAL.items():
        apps.setdefault(q, []).extend(_verify_app(s, q) for s in specs)
    return apps


def overall(key, qid, applied):
    if qid in SPECIAL:
        return SPECIAL[qid][0], SPECIAL[qid][1]
    if qid in STEP3_NOT_APPLIED:
        return "BLOCKED", STEP3_NOT_APPLIED[qid]
    if qid in STEP3_PARTIAL:
        return "PARTIAL", STEP3_PARTIAL[qid][0]
    if qid in A9_9_PARTIAL:
        return "PARTIAL", A9_9_PARTIAL[qid]
    if key == "A9.9" or qid in STEP3:
        if not any(a["lane"] in ("STEP2", "STEP3", "A9.13_DATA", "A9.17") for a in applied):
            return "BLOCKED", "no step-2 / step-3 application verified"
    if qid in NOT_APPLICABLE:
        return "NOT_APPLICABLE_TO_ARTIFACTS", NOT_APPLICABLE[qid]
    governing = [a for a in applied if a["artifact"] != "docs/budgets/owner_decisions/owner_questions_state_v5.json"]
    if governing:
        return "APPLIED", None
    return "BLOCKED", "no governing artifact application"


def build():
    lane = lane_applications()
    rep = repair_applications()
    integ, a915_integ = integration_applications()
    code = code_applications()
    entries = []
    for key in L.ORDER:
        if key == "A9.15":
            continue
        for qid in L.decision_ids(key):
            a = L.answer(qid)
            applied = (lane.get(qid, []) + rep.get(qid, []) + integ.get(qid, []) + EXTRA_APPS.get(qid, [])
                       + code.get(qid, []))
            st, reason = overall(key, qid, applied)
            e = {"decision": key, "question_id": qid, "sequenced_no": a["sequenced_no"],
                 "decision_code": a["decision_code"], "decision_json": a["decision_json"],
                 "decision_json_sha256": a["decision_json_sha256"], "status": st}
            if reason:
                e["status_reason"] = reason
            if "amended_by" in a:
                e["amended_by_a9_15"] = a["amended_by"]["verbatim_excerpt"]
            if a["rfp_citation_status"]:
                e["rfp_citation_status"] = a["rfp_citation_status"]
            e["applications"] = applied
            e["residual"] = [{"status": s, "what": w, "where": wh} for s, w, wh in RESIDUAL.get(qid, [])]
            if qid in STEP3_NOT_APPLIED:
                e["residual"].append({"status": "BLOCKED", "what": STEP3[qid], "where": F_REGEN_WHERE})
            elif qid in STEP3_PARTIAL:
                e["residual"].append({"status": "BLOCKED", "what": "surface v2 build over the registered AOCS "
                                      "pointing envelope (envelope not registered)", "where": "spacecraft / AOCS ICD "
                                                                                              "(owner)"})
            elif (qid in STEP3 or (key == "A9.9" and qid not in A9_9_PARTIAL)) \
                    and not any(r["status"] == "PENDING_FINALIZE_DESIGN_REGEN" for r in e["residual"]):
                e["residual"].append({"status": "PENDING_FINALIZE_DESIGN_REGEN", "what": F_REGEN,
                                      "where": F_REGEN_WHERE})
            if qid in A9_9_PARTIAL:
                e["residual"].append({"status": "BLOCKED", "what": "intake surface v2 build (rule-1 versioned) waits "
                                      "for the registered AOCS pointing envelope (A9.13 S6.2 / F1Q-03)",
                                      "where": "spacecraft / AOCS ICD (owner); abep_sim/data/ build"})
            if qid in RESOLVED_RESIDUAL:
                ptrs = [a.get("record_pointer") for a in applied if a["lane"] == "M16_V5"]
                if len(ptrs) != 1 or not ptrs[0]:
                    raise SystemExit(f"{qid}: resolved residual without one verified M16 v5 record")
                e["resolved_residual"] = [{**x, "record_pointer": ptrs[0]} for x in RESOLVED_RESIDUAL[qid]]
            if qid in RESOLVED_RESIDUAL_AG15:
                e["resolved_residual"] = e.get("resolved_residual", []) + ag15_resolved(qid)
            entries.append(e)
    a15 = L.LOADED["A9.15"]
    a915_apps = [{"lane": ln, "artifact": LANES[ln][1], "commit": LANES[ln][0], "status": "APPLIED",
                  "record_locations": _locations(json.loads((ROOT / LANES[ln][1]).read_text(encoding="utf-8")),
                                                 "A9.15"), "what": w} for ln, w in A915_APPLIED.items()]
    a915_apps += [{"lane": ln, "artifact": LANES[ln][1], "commit": LANES[ln][0], "status": "NOT_APPLICABLE_TO_ARTIFACTS",
                   "what": w} for ln, w in A915_REVIEWED_NA.items()]
    a915_apps += a915_integ
    a915_apps += [_verify_app(_app("STEP3", "abep_sim/design/upstream_a9_13.py", DESIGN_LAYER_COMMIT,
                                   ["A9.15 propellants", "PROPELLANT_POLICY = {"],
                                   "design layer: ambient air AND Xe capability, two separate propellant tanks / "
                                   "paths (PROPELLANT_POLICY, AIR_PATH / XE_PATH)"), "A9.15"),
                  _verify_app(_app("A9.22", "abep_sim/assessment/design_gates.py", A922_DESIGN_SEPARATION_COMMIT,
                                   ["def propellant_paths_check", "A9.15 / RFP-P18-08"],
                                   "assessment layer (A9.22 layer separation moved it from the design layer; "
                                   "upstream_a9_13 keeps a deprecated shim): HC-10 structural check of the two "
                                   "separate propellant tanks / paths (propellant_paths_check)"), "A9.15"),
                  _verify_app(_app("STEP3", "docs/requirements/rvm_a9/rfp_rebase.py", RVM_REBASE_COMMIT, ["A9.15"],
                                   "RVM re-base on the registered RFP carries the A9.15 propellant policy"), "A9.15")]
    for x in a915_apps:
        if x["status"] == "APPLIED" and not x.get("record_locations"):
            raise SystemExit(f"A9.15 application in {x['artifact']} has no locatable record")
    entries.append({"decision": "A9.15", "question_id": "A9.15 governing_rule", "sequenced_no": None,
                    "decision_code": a15["doc"]["decision"], "decision_json": a15["json"],
                    "decision_json_sha256": a15["json_sha256"], "status": "APPLIED",
                    "amends": list(L.A915_AMENDED) + ["A9.13 owner_statements.xenon"],
                    "rfp_citation_status": L.RFP_PENDING, "applications": a915_apps,
                    "residual": [{"status": "PENDING_OWNER_ACCEPTANCE", "what": "the RFP is now registered by sha256 "
                                  "(A9.17 RFP; docs/requirements/rfp_official/rfp_registration_v1.json) and the RVM "
                                  "re-based on it, but AG-15 is not closed by the owner (requirement_frozen stays "
                                  "false); the OWNER_STATED_PENDING_RFP_REGISTRATION labels of the step-1 records are "
                                  "history of that state", "where": "owner act (AG-15 closure)"}]})
    for dk in LATER:
        if set(X.item_keys(dk)) != {q for (d, q) in LATER_APPS if d == dk}:
            raise SystemExit(f"{dk}: decision items {X.item_keys(dk)} not all covered by LATER_APPS")
    for (dk, qid), specs in sorted(LATER_APPS.items(), key=lambda kv: (LATER.index(kv[0][0]),
                                                                        X.item_keys(kv[0][0]).index(kv[0][1]))):
        d = X.LOADED[dk]
        apps = [_verify_app(s, f"{dk} {qid}") for s in specs]
        governing = [a for a in apps if a["artifact"] not in (V5_REL,)]
        st, reason = LATER_STATUS.get((dk, qid), ("APPLIED" if governing else "BLOCKED",
                                                  None if governing else "no governing artifact application"))
        e = {"decision": dk, "question_id": qid, "sequenced_no": None, "decision_code": X.decision_code(dk, qid),
             "decision_json": d["json"], "decision_json_sha256": d["json_sha256"], "pointer": X.pointer(dk, qid),
             "status": st}
        if reason:
            e["status_reason"] = reason
        e["applications"] = apps
        e["residual"] = [{"status": s, "what": w, "where": wh} for s, w, wh in LATER_RESIDUAL.get((dk, qid), [])]
        if (dk, qid) in RESOLVED_RESIDUAL_AG15:
            e["resolved_residual"] = ag15_resolved((dk, qid))
        entries.append(e)
    apply_later_amendments(entries)
    ag15 = ag_15_record()
    for e in entries:
        if e["question_id"] == "F9-OQ-03":
            e["ag_15"] = ag15
    counts, rcounts = {}, {}
    for e in entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
        for r in e["residual"]:
            rcounts[r["status"]] = rcounts.get(r["status"], 0) + 1
    ids_by_dec = {k: len(L.decision_ids(k)) for k in L.ORDER if k != "A9.15"}
    ids_by_dec.update({dk: len(X.item_keys(dk)) for dk in LATER})
    return {
        "schema": "a9_16_application_matrix_v1", "id": "a9_16_application_matrix_v1",
        "lane": "A9.16 step 1 integration; refreshed in the A9.16 finalize records lane (step 2 / step 3 / A9.17 / "
                "A9.18 applications) and in the A9.17 .. A9.21 records lane (A9.19 / A9.20 / A9.21) and in the A9.22 AG-15 closure lane (G3) and the A9.22 governed migration lanes (G1, G2, G4 .. G9)", "date": "2026-10-03",
        "generated_by": "docs/decisions/application/build_a9_16_application_matrix.py",
        "companion_document": REL(OUT_MD), "test": "tests/test_decision_application_a9_16.py",
        "status_vocabulary": STATUSES, "residual_status_vocabulary": list(RESIDUAL_STATUSES),
        "rule": "one entry per decision id of A9.8 .. A9.14, the A9.15 governing rule and one entry per decision item "
                "of A9.17 .. A9.22; the verbatim .md governs; statuses never PASS; an application is listed only when "
                "its question id (step-1 lanes) or its recorded locator tokens (step 2 / step 3 / A9.17 .. A9.22) are "
                "locatable in the artifact",
        "pins": L.pins() + X.pins(),
        "later_application_commits": {"a9_19_rvm": A919_RVM_COMMIT, "a9_19_budgets": A919_BUDGETS_COMMIT,
                                      "a9_19_design": A919_DESIGN_COMMIT, "a9_19_integration": A919_INTEGRATION_COMMIT,
                                      "a9_17_21_records": RECORDS_A917_21_COMMIT, "a9_22_ag15_closure": A922_AG15_COMMIT,
                                      "a9_21_al08_budgets": A921_AL08_BUDGETS_COMMIT,
                                      "a9_21_icp_gate": A921_ICP_GATE_COMMIT,
                                      "m16_v5_rederivation": M16V5_COMMIT},
        "post_step1_commits": {"step2_merge": "f9f4749994ea17703b005c84aadfb3b04d0cff10", "design_layer": DESIGN_LAYER_COMMIT,
                               "rvm_rfp_rebase": RVM_REBASE_COMMIT},
        "integration_commits": INTEGRATION_COMMITS,
        "repair_commit": REPAIR_COMMIT,
        "repair_fixes": REPAIR_FIXES,
        "lane_commits": {k: v[0] for k, v in LANES.items()},
        "decision_id_counts": ids_by_dec,
        "counts": dict(sorted(counts.items())),
        "residual_counts": dict(sorted(rcounts.items())),
        "rules": RULES,
        "entries": entries,
        "superseded_statements": [{"id": "A9.13 owner_statements.xenon",
                                   "text": L.LOADED["A9.13"]["doc"]["owner_statements"]["xenon"],
                                   "superseded_by": "A9.15 governing_rule"}],
        "builders_check_summary": "A9.16 repair lane: state v4, RFQ v2, mass-power v2, Xe v2 and the F0 performance "
                                  "baseline --check reproduce again (COR-01 / 02 / 05); P1, P2, P3 v1 + v2, P4, RVM, "
                                  "mass-power v3, Xe v3, RFQ v3, state v5, M16 v4, H-1, F9 rebuilt; F4 regenerated "
                                  "(COR-03); F7 / F8 not regenerated (COR-04: the build did not finish inside the "
                                  "2-minute command limit) - its pins to F6 / H-1 / F4 stay stale and "
                                  "tests/test_design_f7_f8_optimizer.py::test_pins_hold stays red until a run "
                                  "without that limit. A9.16 finalize records lane: every builder under "
                                  "docs/requirements, docs/budgets, docs/decisions/application, docs/procurement/"
                                  "rfq_a9_v3, docs/traceability and docs/experiments/hall_icp/integration --check "
                                  "current except M16 v4 (regenerated for the RVM RFP re-base); the RTM is NOT "
                                  "re-pointed to golden_v2.json (see A9.18 GOLDEN residual: a pinned historical "
                                  "record); F-lane records are regenerated by the parallel finalize design lane "
                                  "(PENDING_FINALIZE_DESIGN_REGEN here)",
    }


def apply_later_amendments(entries):
    """Earlier entries amended / superseded by A9.19 / A9.20 / A9.21 (read from the state v5 later_owner_decisions)."""
    v5 = json.loads((ROOT / V5_REL).read_text(encoding="utf-8"))
    later = {}
    for r in v5["rows"]:
        recs = [x for x in r.get("later_owner_decisions", []) if x["relation"] in ("SUPERSEDES", "AMENDS")]
        if recs:
            later[r["id"]] = recs
    sup15 = v5["superseded_statements_a9_19"]
    seen = set()
    for e in entries:
        qid = e["question_id"]
        if e["decision"] in LATER:
            continue
        if qid == "A9.15 governing_rule":
            e["amended_by_later"] = [{"decision": s["superseded_by"]["decision"], "item": "amends/A9.15",
                                      "relation": "AMENDS", "pointer": s["superseded_by"]["pointer"],
                                      "decision_json_sha256": s["superseded_by"]["sha256"],
                                      "scope": s["scope"] + " - superseded statement: " + s["text"]} for s in sup15]
            continue
        if qid not in later:
            continue
        seen.add(qid)
        e["amended_by_later"] = [{k: x[k] for k in ("decision", "item", "relation", "pointer", "decision_json_sha256",
                                                    "scope")} for x in later[qid]]
        if any(x["relation"] == "SUPERSEDES" for x in later[qid]):
            e["status"] = "SUPERSEDED_BY_LATER_DECISION"
            e["status_reason"] = ("applied earlier (applications kept below); superseded by " + ", ".join(sorted(
                {x["decision"] for x in later[qid]})) + ": no C1 flight variant / no conventional hollow cathode; C1 a "
                "ground-only laboratory reference")
    entry_ids = {e["question_id"] for e in entries if e["decision"] not in LATER}
    missing = sorted(q for q in later if q in entry_ids and q not in seen)
    if missing:
        raise SystemExit(f"later amendments not attached: {missing}")


def ag15_resolved(key):
    """Resolved AG-15 residual (A9.22 G3): verified against the RVM closure record (tokens + decision sha256)."""
    rel = "docs/requirements/rvm_a9/rvm_a9_v1.json"
    text = (ROOT / rel).read_text(encoding="utf-8")
    if any(t not in text for t in AG15_CLOSURE_TOKENS):
        raise SystemExit(f"{key}: AG-15 closure record not found in {rel} (resolved residual not verifiable)")
    cl = json.loads(text)["rfp_rebase"]["ag15_closure"]
    if cl["decision"]["json_sha256"] != X.LOADED["A9.22"]["json_sha256"]:
        raise SystemExit(f"{key}: RVM ag15_closure does not cite the pinned A9.22 record")
    return [dict(x) for x in RESOLVED_RESIDUAL_AG15[key]]


def ag_15_record():
    """AG-15 (A9.13 S6.22 / F9-OQ-03): registration + RVM re-base APPLIED; owner acceptance APPLIED by A9.22 G3 only when
    the RVM closure record, the registration page review and the F9 AG-15 gate agree with the pinned A9.22 record
    (fail closed); otherwise PENDING_OWNER_ACCEPTANCE."""
    reg = json.loads((ROOT / REG_REL).read_text(encoding="utf-8"))
    rvm = json.loads((ROOT / RVM_REL).read_text(encoding="utf-8"))
    doc, rb = reg["document"], rvm["rfp_rebase"]
    if reg["status"] != "REGISTERED_BY_HASH_PDF_CONTROLLED_EXTERNALLY" or len(doc.get("sha256", "")) != 64:
        raise SystemExit("AG-15: RFP registration missing or not REGISTERED_BY_HASH_PDF_CONTROLLED_EXTERNALLY")
    if rb["registration"]["pdf_sha256"] != doc["sha256"] or rb["registration"]["n_clauses"] != len(reg["clauses"]):
        raise SystemExit("AG-15: RVM re-base does not match the registered RFP (sha256 / clause count)")
    unmapped = [c["clause_id"] for c in rb["clause_coverage"] if not c["rvm_rows"] and not c.get("not_system_requirement")]
    if unmapped or len(rb["clause_coverage"]) != len(reg["clauses"]):
        raise SystemExit(f"AG-15: registered clauses not covered by the RVM re-base: {unmapped}")
    frozen = [r["id"] for r in rvm["rows"] if r["category"].startswith("rfp") and r.get("requirement_frozen")]
    rfp_rows = [r["id"] for r in rvm["rows"] if r["requirement_origin"] == "RFP_CLAUSE"]
    cl = rb.get("ag15_closure")
    if cl is None:
        if frozen:
            raise SystemExit("AG-15: RFP rows frozen without an owner closure record")
        acceptance = {"status": "PENDING_OWNER_ACCEPTANCE", "rfp_rows_requirement_frozen": frozen,
                      "what": "owner acceptance of the re-base / AG-15 closure (" + rb["ag_15_status"] + ")"}
    else:
        d = X.LOADED["A9.22"]
        f9 = json.loads((ROOT / F9_REL).read_text(encoding="utf-8"))
        g = [x for x in f9["architecture_gates"] if x["id"] == "AG-15"]
        pr = reg["page_coverage"].get("owner_page_review") or {}
        if (cl["decision"]["json"], cl["decision"]["json_sha256"]) != (d["json"], d["json_sha256"]) \
                or cl["frozen_rows"] != rfp_rows or sorted(frozen) != sorted(rfp_rows) \
                or pr.get("decision", {}).get("json_sha256") != d["json_sha256"] \
                or len(g) != 1 or g[0]["evidence_sufficient_for_freeze"] is not True:
            raise SystemExit("AG-15: closure record / registration page review / F9 AG-15 gate disagree with the "
                             "pinned A9.22 G3 record (fail closed)")
        acceptance = {"status": "APPLIED", "by": "A9.22 G3_REQUIREMENTS_SNAPSHOT",
                      "decision_json": d["json"], "decision_json_sha256": d["json_sha256"],
                      "decision_md": d["md"], "decision_md_sha256": d["md_sha256"],
                      "decision_code": X.decision_code("A9.22", "G3_REQUIREMENTS_SNAPSHOT"),
                      "artifact": RVM_REL, "record_pointer": AG15_CLOSURE_POINTER, "commit": A922_AG15_COMMIT,
                      "rfp_rows_requirement_frozen": frozen, "requirements_snapshot": rb["requirements_snapshot"],
                      "f9_gate": g[0]["current_status"],
                      "what": "owner closure of AG-15 (requirement basis frozen; no RVM status changed, no compliance "
                              "claim)"}
    return {
        "gate": "AG-15 (A9.13 S6.22 F9-OQ-03; A9.17 RFP)",
        "registration": {"status": "APPLIED", "artifact": REG_REL, "commit": "96ace704ed78d699c5805ebcc8acd99f5cc0b125",
                         "registered_status": reg["status"], "pdf_sha256": doc["sha256"], "pages": doc["pages"],
                         "n_clauses": len(reg["clauses"]), "pdf_in_repository": doc["committed_to_repository"]},
        "rvm_rebase": {"status": "APPLIED", "artifact": RVM_REL, "builder": "docs/requirements/rvm_a9/rfp_rebase.py",
                       "commit": RVM_REBASE_COMMIT, "id": rb["id"], "clauses_covered": len(rb["clause_coverage"]),
                       "origin_counts": rb["origin_counts"]},
        "owner_acceptance": acceptance}


def _c(s):
    return " ".join(str(s).split()).replace("|", "\\|")


def render_md(doc):
    out = ["# A9.16 decision-application matrix", "",
           f"Generated by `{doc['generated_by']}` (do not edit by hand; `--check` verifies). {doc['rule']}.", "",
           "Counts: " + ", ".join(f"{k} {v}" for k, v in doc["counts"].items()) + ". Residual items: "
           + ", ".join(f"{k} {v}" for k, v in doc["residual_counts"].items()) + ".", "",
           "Integration commits: " + ", ".join(f"{k} `{v}`" for k, v in doc["integration_commits"].items())
           + ". Lane commits: " + ", ".join(f"{k} `{v[:7]}`" for k, v in doc["lane_commits"].items()) + ".", "",
           "## Rules recorded", ""]
    out += [f"- **{r['id']}** ({r['status']}): {_c(r['rule'])} - {_c(r['application'])}" for r in doc["rules"]]
    out += ["", "## Entries", "", "| decision | id | seq | code | status | applied in (lane: artifact @ commit) | residual |",
            "|---|---|---|---|---|---|---|"]
    for e in doc["entries"]:
        apps = "; ".join(f"{a['lane']}: {a['artifact'].rsplit('/', 1)[-1]} @ {a['commit'][:7]}"
                         + ("" if a["status"] == "APPLIED" else f" ({a['status']})") for a in e["applications"])
        res = "; ".join(f"{r['status']}: {r['what']}" for r in e["residual"])
        res += "".join(f"; resolved {r['status_before']} -> {r['status']} ({r['artifact'].rsplit('/', 1)[-1]} @ "
                       f"{r['commit'][:7]} {r['record_pointer']}): {r['what']}" for r in e.get("resolved_residual", []))
        st = e["status"] + (f" - {e['status_reason']}" if e.get("status_reason") else "")
        if e.get("amended_by_later"):
            st += " (later: " + "; ".join(f"{x['relation']} by {x['decision']} {x['item']}"
                                          for x in e["amended_by_later"]) + ")"
        out.append(f"| {e['decision']} | {e['question_id']} | {e['sequenced_no'] or '-'} | {e['decision_code'] or '-'} | "
                   f"{_c(st)} | {_c(apps) or '-'} | {_c(res) or '-'} |")
    out += ["", "## Pins", ""] + [f"- `{p['path']}` sha256 `{p['sha256']}`" for p in doc["pins"]]
    out += ["", "No PASS; no question answered here. The official RFP is registered by hash (A9.17 RFP) and the RVM "
            "re-based; step-1 rfp_citation_status OWNER_STATED_PENDING_RFP_REGISTRATION labels are history; AG-15 is "
            "closed by the owner (A9.22 G3; requirement basis frozen, not compliance)."]
    return "\n".join(out) + "\n"


def outputs(doc=None):
    doc = doc or build()
    return {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_md(doc)}


def main():
    outs = outputs()
    if "--check" in sys.argv:
        stale = [p.name for p, s in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != s]
        if stale:
            raise SystemExit(f"A9.16 application matrix stale: {stale}")
        print("A9.16 application matrix: current")
        return
    for p, s in outs.items():
        p.write_text(s, encoding="utf-8")
    d = json.loads(outs[OUT_JSON])
    print("wrote A9.16 application matrix: " + json.dumps(d["counts"]))


if __name__ == "__main__":
    main()
