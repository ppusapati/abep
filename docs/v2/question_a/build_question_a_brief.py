#!/usr/bin/env python3
"""Build (or --check) docs/v2/question_a/question_a_brief.json.

v2 Question A owner-decision brief (lane fo_v2_domain_question_a, trigger T_V2_QUESTION_A).
Status DRAFT_PENDING_OWNER. It decides nothing.

Every number in the output JSON is copied from a verified lane file and carries {file, field}, or it is
derived here from such numbers by the explicit rule in `derived_bounds` (integer counting only). No
physical value, efficiency or threshold is introduced here.

Inputs are read READ-ONLY and pinned by sha256. They are resolved in this order:
  1. the file at its repository path in this checkout;
  2. `git show <commit>:<path>` from the lane commit (shared object store);
  3. any `<root>/.claude/worktrees/*/<path>`.
A pinned input that cannot be found with the pinned sha256 raises InputMissing (no fallback values).

Usage:
  python docs/v2/question_a/build_question_a_brief.py            # write question_a_brief.json
  python docs/v2/question_a/build_question_a_brief.py --check    # rebuild and compare (exit 1 on difference)
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "question_a_brief.json")
BRIEF_MD = "docs/v2/question_a/QUESTION_A_BRIEF.md"
SELF = "docs/v2/question_a/build_question_a_brief.py"

LANE01 = "lane_01_n2_domain_extension"
LANE01_COMMIT = "0636634ae7adf8790b0dc42ccb26138909bad92e"
LANE01_WORKTREE_AT_AUTHORING = "/home/user/abep/.claude/worktrees/wf_17c9b0e6-1cb-2"
LANE02 = "lane_02_ood_attribution"
LANE02_COMMIT = "5e5c8a7bee07da0148a8076497958b2372604418"
LANE02_WORKTREE_AT_AUTHORING = "/home/user/abep/.claude/worktrees/wf_17c9b0e6-1cb-1"
BASE_COMMIT = "2aea8090e613baf4c36037c88d54f2ea42edbfb9"

AUDIT = "docs/chemistry/n2_domain_extension/domain_extension_audit.json"
REQ = "docs/chemistry/n2_domain_extension/domain_extension_requirements.json"
AUDIT_MD = "docs/chemistry/n2_domain_extension/N2_DOMAIN_EXTENSION_AUDIT.md"
OUTLINE = "docs/chemistry/n2_domain_extension/drafts/p5_n2_validation_v2_prereg_OUTLINE_DRAFT.md"
OOD = "docs/forensics/p5_n2_v1/ood_attribution/ood_attribution.json"
OOD_MD = "docs/forensics/p5_n2_v1/ood_attribution/OOD_ATTRIBUTION.md"
OPMODEL = "docs/orchestration/OPERATING_MODEL.md"
CRITERIA = "hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json"

INPUTS = {
    AUDIT: {"lane": LANE01, "commit": LANE01_COMMIT, "worktree_at_authoring": LANE01_WORKTREE_AT_AUTHORING,
            "sha256": "7c7af7128f63a7cc6e26f78cd7e14b1994e4c0e17fda0383f588eff42ec8d87b"},
    REQ: {"lane": LANE01, "commit": LANE01_COMMIT, "worktree_at_authoring": LANE01_WORKTREE_AT_AUTHORING,
          "sha256": "d8aa8d04a4071e513a80ff53d7350919a927eabf85280be69c5e7f11bc907a58"},
    AUDIT_MD: {"lane": LANE01, "commit": LANE01_COMMIT, "worktree_at_authoring": LANE01_WORKTREE_AT_AUTHORING,
               "sha256": "ffe2c5cbc407aa9fd08a99928bd66c9c6c4af000a4516372dbbee6dd3717f1cb"},
    OUTLINE: {"lane": LANE01, "commit": LANE01_COMMIT, "worktree_at_authoring": LANE01_WORKTREE_AT_AUTHORING,
              "sha256": "e41c43ec24a08b2ae4c0838bb4f6b94d0cc33c00f44bcd892dedd94126f76ce9"},
    OOD: {"lane": LANE02, "commit": LANE02_COMMIT, "worktree_at_authoring": LANE02_WORKTREE_AT_AUTHORING,
          "sha256": "5c69fe1b4507566b11a69ab442c68362d5d2f52adda2bddd85ae11a2b8592660"},
    OOD_MD: {"lane": LANE02, "commit": LANE02_COMMIT, "worktree_at_authoring": LANE02_WORKTREE_AT_AUTHORING,
             "sha256": "6fcc8ba0829571664de8905765926299a2a750c128e8450a25fa905bf24d7379"},
    OPMODEL: {"lane": "base", "commit": BASE_COMMIT, "worktree_at_authoring": None,
              "sha256": "642955e35f32e5112f733f35e43d9a69764258a307c9f00142659c63695e0ed6"},
    CRITERIA: {"lane": "base", "commit": BASE_COMMIT, "worktree_at_authoring": None,
               "sha256": "8ca75ae2fac3a47ba008474f706cdfa8b60e3d1cf27429e1a4ad55dc47068462"},
}

FAMILIES = ("dissociation", "electronic", "rotational", "vibrational")
EXPECTED_FAMILY_SIZES = {"dissociation": 1, "electronic": 8, "rotational": 2, "vibrational": 10}
VERDICTS = ("SUPPORTED", "PARTIAL", "UNSUPPORTED", "UNRESOLVED-BY-SOURCE")
CANDIDATE_LIMITS = ("60", "75", "90", "120", "150")
OPTION_IDS = ("A-NO", "A-PARTIAL", "A-YES-WITH-CONDITIONS")


class InputMissing(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _search_roots() -> list[str]:
    roots = [REPO]
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=REPO,
                                capture_output=True, text=True, check=True).stdout.strip()
        roots.append(os.path.dirname(common))
    except (OSError, subprocess.CalledProcessError):
        pass
    out = []
    for r in roots:
        for c in [r] + sorted(glob.glob(os.path.join(r, ".claude", "worktrees", "*"))):
            if c not in out:
                out.append(c)
    return out


def read_input(path: str) -> tuple[bytes, str]:
    """Return (bytes, how_resolved) for a pinned input, verified by sha256."""
    spec = INPUTS[path]
    want = spec["sha256"]
    local = os.path.join(REPO, path)
    if os.path.isfile(local):
        with open(local, "rb") as fh:
            data = fh.read()
        if _sha(data) == want:
            return data, "checkout"
    try:
        data = subprocess.run(["git", "show", f"{spec['commit']}:{path}"], cwd=REPO, capture_output=True,
                              check=True).stdout
        if _sha(data) == want:
            return data, f"git show {spec['commit'][:7]}"
    except (OSError, subprocess.CalledProcessError):
        pass
    for root in _search_roots():
        cand = os.path.join(root, path)
        if os.path.isfile(cand):
            with open(cand, "rb") as fh:
                data = fh.read()
            if _sha(data) == want:
                return data, "worktree"
    raise InputMissing(f"pinned input not found with sha256 {want[:12]}...: {path} "
                       f"(lane {spec['lane']}, commit {spec['commit'][:7]})")


def load_json(path: str):
    return json.loads(read_input(path)[0].decode("utf-8"))


def get(obj, dotted: list):
    cur = obj
    for k in dotted:
        cur = cur[k]
    return cur


def num(file: str, obj, field: list, name: str | None = None) -> dict:
    """A copied number with its provenance {value, file, field}."""
    return {"name": name or str(field[-1]), "value": get(obj, field), "file": file,
            "field": ".".join(str(f) for f in field), "path": list(field)}


# ----------------------------------------------------------------------------------------------------------------
def build() -> dict:
    audit = load_json(AUDIT)
    req = load_json(REQ)
    ood = load_json(OOD)
    crit = load_json(CRITERIA)
    opmodel = read_input(OPMODEL)[0].decode("utf-8")
    outline = read_input(OUTLINE)[0].decode("utf-8")
    audit_md = read_input(AUDIT_MD)[0].decode("utf-8")
    read_input(OOD_MD)  # pinned (cited in the brief), content not parsed

    assert audit["status"] == "DRAFT_PENDING_OWNER"
    tables = audit["tables"]

    # ---------------------------------------------------------------- (1) the question, verbatim
    qa_line = next(line for line in opmodel.splitlines() if "**Question A**" in line)
    question = {
        "verbatim_lane_task": ("does INDEPENDENT PUBLISHED evidence justify expanding the admissible N2 chemistry "
                               "energy domain beyond the pre-registered 45 eV mean energy (T_e 30 eV)?"),
        "verbatim_lane_task_source": "lane fo_v2_domain_question_a task text (workflow harness, trigger T_V2_QUESTION_A)",
        "verbatim_operating_model": qa_line.strip(),
        "verbatim_operating_model_source": f"{OPMODEL} section 4",
        "verbatim_claude_md": "Question A (is a wider domain source-supported?)",
        "verbatim_claude_md_source": "CLAUDE.md, Next work item 3 ('v2 chemistry')",
        "scope_boundary": [
            "Question B (which electronic-excitation representation is supportable) is separate and conditional on "
            "Question A; this brief does not address it.",
            "Johnson-low (n2_n_exc_johnsonlow.toml) remains a sensitivity; this brief does not change that.",
            "The P5-N2 v1 outcome stays INCONCLUSIVE permanently; nothing here re-scores or re-labels a v1 run.",
            "A validity limit is never extended because the solver reached a higher T_e; only independent published "
            "evidence and a new v2 pre-registration can support an extension (CLAUDE.md, critical path after v1).",
        ],
    }

    # ---------------------------------------------------------------- (2) per table family
    fam_tables: dict[str, list[str]] = {f: [] for f in FAMILIES}
    for t in sorted(tables):
        fam_tables[tables[t]["family"]].append(t)
    for f, n in EXPECTED_FAMILY_SIZES.items():
        if len(fam_tables[f]) != n:
            raise ValueError(f"family {f}: expected {n} tables in {AUDIT}, found {len(fam_tables[f])}")

    per_table_keys = ("family", "current_limit_mean_energy_eV", "current_basis", "verdict", "verdict_status",
                      "proposed_extended_limit_mean_energy_eV", "proposal_status", "cited_sources", "provenance_refs",
                      "source_coverage", "construction_above_source", "independent_evidence", "extraction_check",
                      "criteria_numbers", "reasoning", "conditions", "own_source_note",
                      "what_would_change_the_verdict", "key_numbers")
    families = {}
    for f in FAMILIES:
        rows = []
        for t in fam_tables[f]:
            src = tables[t]
            if src["verdict"] not in VERDICTS:
                raise ValueError(f"unknown verdict {src['verdict']!r} for {t}")
            row = {"table": t, "ref": {"file": AUDIT, "field": f"tables.{t}"}}
            for k in per_table_keys:
                if k in src:
                    row[k] = src[k]
            vc = req["verdict_criteria"]["per_table"][t]
            rq = req["requirements"]["per_table"][t]
            cov = {
                "source_last_data_point_eV": num(REQ, req, ["requirements", "per_table", t,
                                                            "source_last_data_point_eV"]),
                "declared_model_above_last_point": num(REQ, req, ["requirements", "per_table", t,
                                                                  "declared_model_above_last_point"]),
            }
            if vc.get("applicable", True):
                for k in ("coverage_end_measured_reading_eV", "coverage_end_evaluated_reading_eV",
                          "L_star_own_sources_eV", "L_star_measured_coverage_eV",
                          "max_candidate_L_measured_reading", "max_candidate_L_evaluated_reading"):
                    cov[k] = num(REQ, req, ["verdict_criteria", "per_table", t, k])
            else:
                cov["verdict_criteria_not_applicable"] = num(REQ, req, ["verdict_criteria", "per_table", t, "reason"])
            ereq = {}
            for L in CANDIDATE_LIMITS:
                bl = rq["by_limit"][L]
                key = "hold_envelope_E_req_eV" if "hold_envelope_E_req_eV" in bl else "flat_sigma_E_req_eV"
                ereq[L] = num(REQ, req, ["requirements", "per_table", t, "by_limit", L, key],
                              name=f"E_req_{key}_at_L_{L}")
            cov["E_req_by_candidate_limit"] = ereq
            if "hold_envelope_is_upper_bound" in rq:
                cov["hold_envelope_is_upper_bound"] = num(REQ, req, ["requirements", "per_table", t,
                                                                     "hold_envelope_is_upper_bound"])
            row["coverage_vs_E_req"] = cov
            row["v1_ood"] = {
                "n_ood_runs_beyond_limit_lane01": num(REQ, req, ["v1_inventory", "tables", t, "n_ood_runs_beyond_limit"]),
                "n_runs_f_out_gt_tol_lane02": num(OOD, ood, ["per_file", t, "n_runs_f_out_gt_tol"]),
                "n_runs_sole_cause_lane02": num(OOD, ood, ["per_file", t, "n_runs_sole_cause"]),
            }
            rows.append(row)
        verdict_counts = {v: sum(1 for r in rows if r["verdict"] == v) for v in VERDICTS}
        supported_limits = {r["table"]: r["proposed_extended_limit_mean_energy_eV"] for r in rows
                            if r["proposed_extended_limit_mean_energy_eV"] is not None}
        families[f] = {
            "n_tables": len(rows),
            "tables": [r["table"] for r in rows],
            "verdicts": {r["table"]: r["verdict"] for r in rows},
            "verdict_counts": verdict_counts,
            "supported_extended_limits_mean_energy_eV_DRAFT": supported_limits,
            "per_table": rows,
        }
    families["dissociation"]["family_caveats"] = [
        {"text": c, "file": AUDIT, "field": f"tables.dissociation_N2.dat.conditions[{i}]"}
        for i, c in enumerate(tables["dissociation_N2.dat"]["conditions"])]
    families["electronic"]["family_caveats"] = [
        {"text": ("a1Pi_g is PARTIAL: measured coverage ends at Johnson's 200 eV point; only the evaluated reading "
                  "(MS1997 via QST secondary reproduction) passes, to 150 eV. The other seven states are "
                  "UNRESOLVED-BY-SOURCE: MS1997 fails the C3 join at 100 eV and Kawaguchi 2021 is abstract-only."),
         "file": AUDIT, "field": "tables.excitation_N2_*.reasoning"},
        {"text": ("The MS1997-Johnson conflict is also present at 50 eV, inside the v1 domain; recorded, not acted on "
                  "(lane-01 audit section 6.2)."), "file": AUDIT_MD, "field": "section 6.2"},
        {"text": ("The Johnson-low variant tables share the nominal continuation above Johnson's last point, so the "
                  "electronic verdicts apply to them unchanged (lane-01 audit section 3). Johnson-low remains a "
                  "sensitivity; which excitation representation is supportable is Question B."),
         "file": AUDIT_MD, "field": "section 3"},
    ]
    families["rotational"]["family_caveats"] = [
        {"text": tables[t]["reasoning"], "file": AUDIT, "field": f"tables.{t}.reasoning"}
        for t in fam_tables["rotational"]] + [
        {"text": ("hold_envelope_is_upper_bound is false for j 0->2 (sigma still rising at 10 eV), so E_req from the "
                  "hold envelope is not conservative for it (lane-01 audit section 5)."),
         "file": REQ, "field": "requirements.per_table.excitation_N2_rot_j0_to_j2.dat.hold_envelope_is_upper_bound"}]
    families["vibrational"]["family_caveats"] = [
        {"text": tables["excitation_N2_vib_0_to_1.dat"]["reasoning"], "file": AUDIT,
         "field": "tables.excitation_N2_vib_0_to_1.dat.reasoning"},
        {"text": tables["excitation_N2_vib_0_to_2.dat"]["reasoning"], "file": AUDIT,
         "field": "tables.excitation_N2_vib_0_to_2.dat.reasoning (same text for 0->2 ... 0->10)"},
        {"text": "E_req is not defined for the vibrational tables (rate fits, no cross section in the repository); "
                 "the flat-sigma reference applies.", "file": REQ,
         "field": "requirements.per_table.excitation_N2_vib_0_to_1.dat.by_limit.*.note"},
    ]

    # ---------------------------------------------------------------- (2b) OOD consequence: counting only
    hc = req["hypothetical_coverage"]
    ladder = {str(int(r["hypothetical_limit_mean_energy_eV"])): i
              for i, r in enumerate(ood["hypothetical_limit_ladder_45eV_family"]["ladder"])}
    scen = {}
    for L in CANDIDATE_LIMITS:
        scen[L] = {s: num(REQ, req, ["hypothetical_coverage", "limits", L, s, "newly_covered_ood_runs"])
                   for s in hc["limits"][L]}
        i = ladder[L]
        scen[L]["lane02_officially_OOD_runs_all_45eV_files_eps_active_le_L"] = num(
            OOD, ood, ["hypothetical_limit_ladder_45eV_family", "ladder", i,
                       "n_officially_OOD_runs_with_all_45eV_files_eps_active_le_L"])
        scen[L]["lane02_candidate_member_cells_all_20_runs_eps_active_le_L_of_108"] = num(
            OOD, ood, ["hypothetical_limit_ladder_45eV_family", "ladder", i,
                       "n_candidate_member_cells_all_20_runs_eps_active_le_L"])
    ood_consequence = {
        "label": "HYPOTHETICAL COUNTING ONLY - not scoring, not a status, not a verdict, not a proposal to change limits",
        "lane01_definition": num(REQ, req, ["hypothetical_coverage", "definition"]),
        "lane02_label": num(OOD, ood, ["hypothetical_limit_ladder_45eV_family", "label"]),
        "lane02_what_it_does_not_imply": num(OOD, ood, ["hypothetical_limit_ladder_45eV_family",
                                                        "what_it_does_not_imply"]),
        "lane02_proxy_bound_on_f_out_at_L": num(OOD, ood, ["hypothetical_limit_ladder_45eV_family",
                                                           "frame_cell_count_for_the_bound",
                                                           "resulting_bound_on_f_out_at_L_when_eps_active_le_L"]),
        "lane02_proxy_bound_evidence_class": num(OOD, ood, ["hypothetical_limit_ladder_45eV_family",
                                                            "frame_cell_count_for_the_bound", "evidence_class"]),
        "v1_totals": {
            "n_records": num(REQ, req, ["v1_inventory", "n_records"]),
            "n_runs_out_of_domain": num(REQ, req, ["v1_inventory", "n_runs_out_of_domain"]),
            "official_status_counts_run_readings": num(REQ, req, ["v1_inventory",
                                                                  "official_status_counts_run_readings"]),
            "n_ood_runs_dissociation_only_beyond": num(REQ, req, ["v1_inventory",
                                                                  "n_ood_runs_dissociation_only_beyond"]),
            "ood_cause_categories_lane02": num(OOD, ood, ["co_occurrence", "category_counts_OOD_runs"]),
            "subfamily_pattern_counts_lane02": num(OOD, ood, ["co_occurrence", "subfamily_pattern_counts"]),
            "proxy_caveat_in_domain_runs_with_eps_active_above_45": num(
                REQ, req, ["hypothetical_coverage", "proxy_caveat_n_in_domain_runs_with_eps_active_above_45"]),
            "official_candidate_member_cells_with_zero_OOD_runs_of_108": num(
                OOD, ood, ["hypothetical_limit_ladder_45eV_family", "empirical_concordance_at_the_recorded_45eV_limit",
                           "official_candidate_member_cells_with_zero_OOD_runs"]),
        },
        "by_candidate_limit": scen,
        "draft_evidence_supported_dissociation_60": {
            "newly_covered_ood_runs_proxy": num(REQ, req, ["draft_proposed_limits_mean_energy_eV",
                                                           "hypothetical_coverage_if_applied",
                                                           "newly_covered_ood_runs"]),
            "remaining_ood_runs_proxy": num(REQ, req, ["draft_proposed_limits_mean_energy_eV",
                                                       "hypothetical_coverage_if_applied", "remaining_ood_runs"]),
            "max_runs_that_can_change_status_exact_under_reproducible_reruns": num(
                REQ, req, ["v1_inventory", "n_ood_runs_dissociation_only_beyond"]),
            "exactness_note": ("Only runs whose beyond-limit set is dissociation alone can change status when only "
                               "dissociation is extended; lane-01 outline section 3 states the 36 / 678 split is exact "
                               "under reproducible reruns, while the 6 is a proxy."),
        },
        "evaluated_reading_dissociation_75_a1Pi_g_150": {
            "limits_not_proposed": num(REQ, req, ["draft_proposed_limits_mean_energy_eV",
                                                  "evaluated_reading_limits_not_proposed"]),
            "newly_covered_ood_runs_proxy": num(REQ, req, ["draft_proposed_limits_mean_energy_eV",
                                                           "hypothetical_coverage_evaluated_reading",
                                                           "newly_covered_ood_runs"]),
            "dissociation_only_at_75_proxy_for_comparison": num(REQ, req, ["hypothetical_coverage", "limits", "75",
                                                                           "dissociation_only_at_L",
                                                                           "newly_covered_ood_runs"]),
        },
    }

    # ---------------------------------------------------------------- derived bounds (integer counting, explicit rule)
    pats = ood["co_occurrence"]["subfamily_pattern_counts"]
    r0_patterns = {p: n for p, n in pats.items() if p.endswith("R0")}
    n_r0 = sum(r0_patterns.values())
    non_d_only_r0 = {p: n for p, n in r0_patterns.items() if p != "D1 E0 V0 R0"}
    cand = ood["breakdown"]["candidate"]
    d_only = {c: v["OOD_categories"]["DISSOCIATION_ONLY"] for c, v in cand.items()}
    max_r0_per_candidate_bound = max(d_only.values()) + sum(non_d_only_r0.values())
    inconcl = ood["breakdown"]["official_member_verdict_vs_OOD_count"]["INCONCLUSIVE"]
    min_ood_inconclusive_member = min(int(k) for k in inconcl)
    n_inconclusive_members = sum(inconcl.values())
    fail_hist = ood["breakdown"]["official_member_verdict_vs_OOD_count"]["FAIL"]
    no_pass_possible = max_r0_per_candidate_bound < min_ood_inconclusive_member
    if not no_pass_possible:
        raise ValueError("derived bound no longer holds; the option texts below assume it does")
    n_ood = req["v1_inventory"]["n_runs_out_of_domain"]
    n_rec = req["v1_inventory"]["n_records"]
    n_d_only = req["v1_inventory"]["n_ood_runs_dissociation_only_beyond"]
    n_not_supported = sum(1 for t in tables if tables[t]["verdict"] != "SUPPORTED")
    derived = {
        "label": ("DERIVED BY COUNTING from lane-02 fields (rule stated below); consequence under stated "
                  "assumptions, not a score, not a verdict, not a prediction of any run status"),
        "script": SELF,
        "assumptions": [
            "minimal v2 in the sense of the lane-01 outline: rate-table contents byte-identical to abep-n2n-0.11, only "
            "validity limits raised, pinned HallThruster.jl, same 30 cases and 9 SGB screening transports, no retuning",
            "reruns reproduce v1 trajectories (lane-01 outline section 3: 'Pinned code gives the same trajectories'; "
            "to be verified by a bit-for-bit reproduction sample)",
            "D1-D6 and O1-O5 unchanged (lane-01 outline section 6, decision 13, default 'no')",
            "limits only rise, so no in-domain v1 run becomes OOD and every v1 FAIL_VALIDATION run keeps its status",
            "the two rotational tables stay at 45 eV (both UNRESOLVED-BY-SOURCE in lane 01; true of every "
            "evidence-supported option in this brief)",
        ],
        "rule": [
            "O3 (criteria v1): a global member PASSes iff all 20 of its runs PASS; FAIL if any run is FAIL_VALIDATION; "
            "otherwise INCONCLUSIVE. A candidate is PROMOTABLE iff some global member PASSes.",
            "A v1 FAIL member contains a FAIL_VALIDATION run, which is unchanged under the assumptions, so it cannot "
            "become PASS.",
            "A v1 INCONCLUSIVE member can become PASS only if every one of its OOD runs leaves OUT_OF_DOMAIN.",
            "With both rotational tables at 45 eV, only OOD runs with no rotational file beyond (pattern '... R0') can "
            "leave OUT_OF_DOMAIN.",
            "Per candidate, such runs number at most DISSOCIATION_ONLY(candidate) + (all R0 runs that are not "
            "dissociation-only); a member is a subset of its candidate's runs.",
            "If that bound is below the smallest OOD count of any v1 INCONCLUSIVE member, no member can reach PASS.",
        ],
        "inputs": {
            "O3_verdicts": num(CRITERIA, crit, ["operational_rules", "O3_verdicts"]),
            "subfamily_pattern_counts": num(OOD, ood, ["co_occurrence", "subfamily_pattern_counts"]),
            "dissociation_only_by_candidate": {c: num(OOD, ood, ["breakdown", "candidate", c, "OOD_categories",
                                                                 "DISSOCIATION_ONLY"]) for c in sorted(cand)},
            "official_member_verdict_vs_OOD_count": num(OOD, ood, ["breakdown",
                                                                   "official_member_verdict_vs_OOD_count"]),
            "lane01_all_capped_except_rotational_at_150": num(REQ, req, ["hypothetical_coverage", "limits", "150",
                                                                         "all_capped_except_rotational_at_L",
                                                                         "newly_covered_ood_runs"]),
        },
        "results": {
            "n_ood_runs_without_rotational_beyond": n_r0,
            "r0_patterns": r0_patterns,
            "max_dissociation_only_runs_per_candidate": max(d_only.values()),
            "upper_bound_r0_ood_runs_per_candidate": max_r0_per_candidate_bound,
            "min_ood_runs_in_any_v1_inconclusive_member": min_ood_inconclusive_member,
            "n_v1_inconclusive_member_cells_of_108": n_inconclusive_members,
            "n_v1_fail_member_cells_of_108": sum(fail_hist.values()),
            "no_member_can_reach_PASS_in_minimal_v2_with_rotational_at_45eV": no_pass_possible,
            "cross_check_equals_lane01_all_except_rotational_at_150": (
                n_r0 == req["hypothetical_coverage"]["limits"]["150"]["all_capped_except_rotational_at_L"]
                ["newly_covered_ood_runs"]),
        },
        "does_not_cover": [
            "a v2 that changes any table (evidence-shaped tail, non-resonant vibration, a process promoted by the "
            "extended-domain re-audit): trajectories change and this bound no longer applies",
            "a v2 with different cases, candidates or criteria",
            "the facility mode (reported with the same aggregation, never gates: criteria v1 O3_verdicts.facility)",
        ],
    }

    # ---------------------------------------------------------------- cross-lane QA checks
    checks = []

    def chk(name, a, b, note=""):
        checks.append({"check": name, "lane01": a, "lane02": b, "equal": a["value"] == b["value"], "note": note})

    chk("n OOD runs", num(REQ, req, ["v1_inventory", "n_runs_out_of_domain"]),
        num(OOD, ood, ["co_occurrence", "n_OOD_runs"]))
    chk("dissociation sole-cause runs", num(REQ, req, ["v1_inventory", "n_ood_runs_dissociation_only_beyond"]),
        num(OOD, ood, ["co_occurrence", "sole_cause_counts", "dissociation_N2.dat"]))
    chk("in-domain runs not proxy-evaluable at 45 eV",
        num(REQ, req, ["hypothetical_coverage", "proxy_caveat_n_in_domain_runs_with_eps_active_above_45"]),
        num(OOD, ood, ["hypothetical_limit_ladder_45eV_family", "empirical_concordance_at_the_recorded_45eV_limit",
                       "n_officially_in_domain_runs_not_proxy_evaluable_at_45"]))
    for L in CANDIDATE_LIMITS:
        chk(f"OOD runs newly covered, all 21 tables at L = {L} eV",
            num(REQ, req, ["hypothetical_coverage", "limits", L, "all_capped_tables_at_L", "newly_covered_ood_runs"]),
            num(OOD, ood, ["hypothetical_limit_ladder_45eV_family", "ladder", ladder[L],
                           "n_officially_OOD_runs_with_all_45eV_files_eps_active_le_L"]))
    for t in sorted(tables):
        chk(f"OOD runs beyond limit: {t}", num(REQ, req, ["v1_inventory", "tables", t, "n_ood_runs_beyond_limit"]),
            num(OOD, ood, ["per_file", t, "n_runs_f_out_gt_tol"]))
    if not all(c["equal"] for c in checks):
        bad = [c["check"] for c in checks if not c["equal"]]
        raise ValueError(f"lane-01 / lane-02 disagree: {bad}")

    observations = [
        {"id": "QA-1", "kind": "definition difference (not a conflict)",
         "text": ("Total covered runs at L differ by definition: lane 01 counts a run covered if every capped table "
                  "had f_out <= 1e-12 in v1 or eps_active <= L (577 at 60 eV), lane 02 requires eps_active <= L for "
                  "every 45 eV-family file (468 at 60 eV). The OOD counts agree at every L (checks above)."),
         "refs": [num(REQ, req, ["hypothetical_coverage", "limits", "60", "all_capped_tables_at_L", "covered_runs"]),
                  num(OOD, ood, ["hypothetical_limit_ladder_45eV_family", "ladder", ladder["60"],
                                 "n_runs_all_45eV_files_eps_active_le_L"])]},
        {"id": "QA-2", "kind": "numbering discrepancy",
         "text": ("Owner-decision numbering differs between lane-01 files: the audit JSON/MD use D-X1..D-X12 with "
                  "D-X12 = the two reconstructed Winters points; the v2 outline section 6 uses 1..14 with 12 = driver "
                  "activity histograms and 14 = Winters points. The outline's section 1 table cites 'owner decision "
                  "14' and its section 3 'owner decision 12' in outline numbering. The mapping is in owner_decisions."),
         "refs": [{"file": AUDIT, "field": "owner_decisions"}, {"file": OUTLINE, "field": "section 6"}]},
        {"id": "QA-3", "kind": "wording difference to be settled by the owner",
         "text": ("Lane 02 states that any extension 'would be a model change with its own reruns'; the lane-01 "
                  "outline treats a limit-only change with byte-identical tables as a minimal v2 that becomes a model "
                  "change only on a table rebuild, an addition or a re-audit promotion. Both require reruns (the frozen "
                  "records hold f_out only at 45 eV). Whether a limit-only change is logged as a model change "
                  "(CLAUDE.md rule 2 / docs/HISTORY.md) is for the owner."),
         "refs": [num(OOD, ood, ["hypothetical_limit_ladder_45eV_family", "what_it_does_not_imply"]),
                  {"file": OUTLINE, "field": "section 1, 'When the minimal v2 becomes a model change'"}]},
        {"id": "QA-4", "kind": "proxy observation",
         "text": ("Under the lane-01 proxy, the evaluated reading (dissociation 75 eV + a1Pi_g 150 eV) newly covers "
                  "the same number of OOD runs as dissociation alone at 75 eV (22 and 22), i.e. the a1Pi_g extension "
                  "adds no proxy-covered run by itself."),
         "refs": [num(REQ, req, ["draft_proposed_limits_mean_energy_eV", "hypothetical_coverage_evaluated_reading",
                                 "newly_covered_ood_runs"]),
                  num(REQ, req, ["hypothetical_coverage", "limits", "75", "dissociation_only_at_L",
                                 "newly_covered_ood_runs"])]},
        {"id": "QA-5", "kind": "open question for the owner (not in the lane files)",
         "text": ("The promotion rule (CLAUDE.md) admits a candidate only after it predicts new evidence not used to "
                  "select it. A v2 scored on the same P5-N2 measurements after the v1 scores are known would need the "
                  "owner to state whether it still counts as such a test; the lane-01 outline requires a hash-locked "
                  "pre-registration before any v2 run."),
         "refs": [{"file": "CLAUDE.md", "field": "Next work 1, Promotion rule"},
                  {"file": OUTLINE, "field": "section 4"}]},
    ]

    # ---------------------------------------------------------------- (3) completeness re-audit items
    ci = audit["completeness_implications"]
    completeness = {
        "status": ci["status"],
        "basis": {"text": ci["basis"], "file": AUDIT, "field": "completeness_implications.basis"},
        "rule": {"text": ci["rule"], "file": AUDIT, "field": "completeness_implications.rule"},
        "domain_for_60eV_limit": {"text": ("re-audit on the extended domain (T_e <= 40 eV for a 60 eV limit), "
                                           "pre-registered and completed before any v2 run"),
                                  "file": OUTLINE, "field": "section 1 table, row 'omitted-process audit'"},
        "items": [dict(item, ref={"file": AUDIT, "field": f"completeness_implications.items[{i}]"})
                  for i, item in enumerate(ci["items"])],
    }

    # ---------------------------------------------------------------- owner decisions (lane-01, verbatim)
    outline_items = []
    in6 = False
    for line in outline.splitlines():
        if line.startswith("## 6."):
            in6 = True
            continue
        if in6 and line.startswith("## "):
            break
        m = re.match(r"^(\d+)\. (.*)$", line)
        if in6 and m:
            outline_items.append([int(m.group(1)), m.group(2)])
        elif in6 and outline_items and line.startswith("   ") and line.strip():
            outline_items[-1][1] += " " + line.strip()
    if [n for n, _ in outline_items] != list(range(1, 15)):
        raise ValueError("outline section 6 is expected to list decisions 1..14")
    dx = audit["owner_decisions"]
    mapping = {1: "D-X1", 2: "D-X2", 3: "D-X3", 4: "D-X4", 5: "D-X5", 6: "D-X6", 7: "D-X7", 8: "D-X8",
               9: "D-X9", 10: "D-X10", 11: "D-X11 (run-scope part)", 12: "D-X11 (driver-histogram part)",
               13: None, 14: "D-X12"}
    owner_decisions = {
        "note": ("All open; copied verbatim. The mapping outline->D-X is this brief's reading (QA-2), not a lane-01 "
                 "statement."),
        "audit_json_D_X": [{"id": s.split(":", 1)[0], "text": s, "file": AUDIT, "field": f"owner_decisions[{i}]"}
                           for i, s in enumerate(dx)],
        "outline_section_6": [{"number": n, "text": s, "maps_to": mapping[n], "file": OUTLINE, "field": "section 6"}
                              for n, s in outline_items],
        "decided": [],
    }
    audit_md_has_12 = "12. Whether two reconstructed Winters points" in audit_md
    owner_decisions["audit_md_section_9_item_12_is_winters_points"] = audit_md_has_12

    # ---------------------------------------------------------------- (4)+(5) options
    sc = ood_consequence["by_candidate_limit"]
    options = [
        {
            "id": "A-NO",
            "title": "No extension is justified",
            "chosen": False,
            "what_it_means": ("All 21 capped tables keep the pre-registered 45 eV mean-energy limit (T_e 30 eV). "
                              "The domain-extension path stops; the lane-01 audit is kept as the recorded negative "
                              "(or insufficient) evidence result."),
            "evidence_position": ("Consistent with lane 01 if the owner rejects D-X12 (two reconstructed Winters "
                                  "points), or adopts a stricter threshold (D-X3: no table is SUPPORTED at 1e-6 or "
                                  "1e-12)."),
            "ood_consequence_counting_only": {
                "newly_chemistry_evaluable_v1_ood_runs": 0,
                "basis": "no limit changes, so the v1 OOD predicate is unchanged",
                "v1_ood_runs": num(REQ, req, ["v1_inventory", "n_runs_out_of_domain"]),
            },
            "consequences": [
                "No v2 is needed for the chemistry domain; a v2 with the same inputs would reproduce v1.",
                "Every v1 INCONCLUSIVE global member stays INCONCLUSIVE and every candidate stays INCONCLUSIVE / NOT "
                "ELIGIBLE; the credible set stays empty on the P5-N2 route (v1 is permanent in any case).",
                "Blocker to record for Hall admission: the pre-registered chemistry domain (T_e <= 30 eV) does not "
                "contain the instantaneous states the screening transports reach at P5-N2 conditions "
                f"({n_ood} of {n_rec} v1 runs OOD), and the accessible published evidence does not support a wider domain.",
                "Question B's precondition ('conditional on that domain', OPERATING_MODEL section 4) is not established; "
                "Question B itself is not addressed here.",
            ],
            "requires_next": [
                "owner decision record (dated) that Question A is answered NO, with the lane-01 audit as its basis",
                "blocker entry for Hall-transport admission naming the chemistry-domain limit and the evidence gaps "
                "(rotational above 10 eV, electronic above 100 eV, non-resonant vibration)",
                "reopening condition: genuinely new published evidence (e.g. via D-X5 legitimate full-text access)",
            ],
            "admission_and_milestone_B": [
                "No scoreable v2 on the P5-N2 route can change the empty credible set.",
                "Milestone B (physics-backed selection) stays blocked on an admitted Hall transport closure; this "
                "option removes the P5-N2 v2 route to one, and admission would need other evidence not identified in "
                "the lane files.",
                "Milestone A (conditional selection) does not need Physics Baseline 1.0; an admitted closure stays "
                "an explicit condition. Milestone C stays blocked behind B.",
            ],
        },
        {
            "id": "A-PARTIAL",
            "title": "Only the evidence-supported extension: dissociation_N2.dat to 60 eV (measured reading)",
            "chosen": False,
            "what_it_means": ("dissociation_N2.dat limit 45 -> 60 eV (lane-01 SUPPORTED, DRAFT), table unchanged; the "
                              "other 20 capped tables stay at 45 eV. Sub-variant (evaluated reading, not proposed by "
                              "lane 01): dissociation 75 eV and a1Pi_g 150 eV, which needs D-X2 = evaluated-inclusive."),
            "evidence_position": ("Rests on two reconstructed Winters 1966 points above 200 eV (about 246 and 296 eV), "
                                  "digitized from Song et al. 2023 Fig. 19 and not independent of Table 9 at the "
                                  "200 eV join (D-X12)."),
            "ood_consequence_counting_only": {
                "proxy_newly_covered_ood_runs": num(REQ, req, ["draft_proposed_limits_mean_energy_eV",
                                                               "hypothetical_coverage_if_applied",
                                                               "newly_covered_ood_runs"]),
                "exact_upper_bound_runs_that_can_change_status": num(REQ, req, ["v1_inventory",
                                                                                 "n_ood_runs_dissociation_only_beyond"]),
                "runs_that_stay_ood_whatever_the_rerun_shows": n_ood - n_d_only,
                "runs_that_stay_ood_basis": ("v1_inventory.n_runs_out_of_domain - "
                                             "v1_inventory.n_ood_runs_dissociation_only_beyond (lane-01 outline "
                                             "section 3: 678 of 714)"),
                "sub_variant_evaluated_reading_proxy": num(REQ, req, ["draft_proposed_limits_mean_energy_eV",
                                                                      "hypothetical_coverage_evaluated_reading",
                                                                      "newly_covered_ood_runs"]),
                "sub_variant_evaluated_reading_exact_upper_bound": n_r0,
                "sub_variant_exact_upper_bound_basis": ("OOD runs with no rotational file beyond (derived_bounds); "
                                                        "which electronic file the single 'D1 E1 V0 R0' run has is "
                                                        f"not published, so the bound is <= {n_r0}"),
            },
            "unblocks": [
                "a pre-registrable v2 limited to one validity-limit change, with byte-identical tables",
                f"chemistry-evaluability of at most {n_d_only} v1 OOD runs "
                f"({req['draft_proposed_limits_mean_energy_eV']['hypothetical_coverage_if_applied']['newly_covered_ood_runs']} "
                "by the proxy); which statuses they would get is not predicted",
            ],
            "does_not_unblock": [
                f"the {n_ood - n_d_only} v1 OOD runs in which an unchanged table is beyond its unchanged limit",
                "any global member PASS in a minimal v2 (derived_bounds: at most "
                f"{max_r0_per_candidate_bound} runs per candidate can leave OOD, every v1 INCONCLUSIVE member has at "
                f"least {min_ood_inconclusive_member} OOD runs, and every v1 FAIL member keeps a FAIL_VALIDATION run); "
                "hence no candidate could become PROMOTABLE in such a v2 and the credible set would stay empty",
                "electronic, rotational and vibrational domains (Question B stays conditional and separate)",
            ],
            "requires_next": [
                "owner decisions D-X12 (Winters points), D-X2 (reading), D-X3 (threshold), D-X4 (C3 tolerance), "
                "D-X6 (held tail unchanged vs rebuild; Kawaguchi -25 % variant)",
                "a pre-registered extended-domain completeness re-audit (T_e <= 40 eV for 60 eV), completed before any "
                "v2 run; any promotion there is a model change (full rerun)",
                "a new versioned rate_validity entry written by the owner under propellants/, with the v1 file and "
                "configs snapshotted (lane-01 outline section 4 step 2)",
                "v2 criteria / run-status rule copies differing only in domain references, hash lock, merged "
                "pre-registration PR before any score-bearing run (outline section 4 steps 3-6)",
                f"run scope D-X11: (A) the {n_d_only} runs that can change status plus a bit-for-bit reproduction sample under a "
                "pre-registered reuse rule, or (B) a clean 1080-run rerun; facility and O4 treatment under v2",
            ],
            "admission_and_milestone_B": [
                f"A scoreable minimal v2 can exist (it can re-score at most {n_d_only} runs), but under the derived_bounds "
                "assumptions it cannot produce a PROMOTABLE candidate; the credible set stays empty.",
                "Admission remains gated on the O4 dispositions (CLAUDE.md; hall_ensemble._check_o4) regardless.",
                "Milestone B stays blocked on an admitted Hall transport closure; Milestone A is unaffected (an "
                "admitted closure stays an explicit condition).",
            ],
        },
        {
            "id": "A-YES-WITH-CONDITIONS",
            "title": "Wider extension across families, only where evidence supports it (not supported today)",
            "chosen": False,
            "what_it_means": ("Raise limits beyond the dissociation-only draft. Lane 01 finds no table other than "
                              "dissociation SUPPORTED: a1Pi_g and the 10 vibrational tables are PARTIAL, 7 electronic "
                              "and 2 rotational tables are UNRESOLVED-BY-SOURCE, none UNSUPPORTED. This option is "
                              "therefore available only after the evidence below exists or the owner changes the "
                              "reading/threshold."),
            "evidence_position": (f"Not supported by the accessible evidence in lane 01 at 60 eV or above for "
                                  f"{n_not_supported} of {len(tables)} tables."),
            "conditions_by_family": {
                f: [{"table": t, "what_would_change_the_verdict": tables[t]["what_would_change_the_verdict"],
                     "file": AUDIT, "field": f"tables.{t}.what_would_change_the_verdict"}
                    for t in fam_tables[f]] for f in FAMILIES},
            "coverage_needed_at_L_60_1pct": {
                t: {"E_req": families[tables[t]["family"]]["per_table"][fam_tables[tables[t]["family"]].index(t)]
                    ["coverage_vs_E_req"]["E_req_by_candidate_limit"]["60"],
                    "source_last_data_point_eV": num(REQ, req, ["requirements", "per_table", t,
                                                                "source_last_data_point_eV"])}
                for t in sorted(tables)},
            "stricter_thresholds": ("At 1e-6 or 1e-12 no measured set reaches E_req, so no table would be SUPPORTED "
                                    "(lane-01 audit section 7; D-X3)."),
            "ood_consequence_counting_only": {
                "all_21_tables_raised_to_L_proxy": {L: sc[L]["all_capped_tables_at_L"] for L in CANDIDATE_LIMITS},
                "cells_all_20_runs_eps_le_L_of_108_proxy": {
                    L: sc[L]["lane02_candidate_member_cells_all_20_runs_eps_active_le_L_of_108"]
                    for L in CANDIDATE_LIMITS},
                "all_but_rotational_raised_proxy": {L: sc[L]["all_capped_except_rotational_at_L"]
                                                    for L in CANDIDATE_LIMITS},
                "note": ("Proxy counts are neither sufficient nor necessary for f_out <= 1e-12 at L (lane 02). A cell "
                         "with all 20 runs evaluable is necessary, not sufficient, for a member PASS: its runs must "
                         "also PASS D1-D6."),
            },
            "requires_next": [
                "rotational: published sigma above 10 eV, or owner acceptance of a theory-only envelope (D-X8); "
                f"without it at most {n_r0} v1 OOD runs can leave OOD (derived_bounds)",
                "electronic: numerical Kawaguchi 2021 ICS or measured ICS above 100 eV (a1Pi_g above 200 eV) through "
                "legitimate access (D-X5); decision on the MS1997-Johnson conflict (D-X9)",
                "vibrational: bound or add non-resonant excitation (D-X7); adding it is a model change",
                "dissociation beyond 60 eV: " + tables["dissociation_N2.dat"]["what_would_change_the_verdict"][0],
                "the extended-domain completeness re-audit on the wider domain (D-X10), which may add processes "
                "(N^2+ -> N^3+ with threshold 47.45 eV inside it, N2^2+, higher states, multiple ionization)",
                "full v2 pre-registration and, for any table change, a new reaction-set version and full rerun",
            ],
            "admission_and_milestone_B": [
                "Only this option could make the rotational-limited majority of v1 OOD runs chemistry-evaluable; "
                "without a rotational extension the derived bound (no member PASS in a minimal v2) still holds.",
                "If any table changes, it is a model change: all runs rerun and nothing from v1 predicts v2 statuses.",
                "Admission stays gated on O4 dispositions; Milestone B stays blocked until a closure is admitted.",
            ],
        },
    ]

    milestones = {
        "supports": ["B (records what blocks physics-backed selection on the chemistry-domain side)",
                     "A (input only: an admitted Hall closure remains an explicit condition of any conditional "
                     "selection; A does not require Physics Baseline 1.0)"],
        "to_reach_next": ("Owner answer to Question A; then, only for A-PARTIAL / A-YES-WITH-CONDITIONS: the "
                          "extended-domain completeness re-audit, a hash-locked v2 pre-registration, the v2 runs, "
                          "the O4 dispositions and an admission decision before Milestone B can use absolute Hall "
                          "performance."),
    }

    return {
        "id": "v2_question_a_brief_v1",
        "status": "DRAFT_PENDING_OWNER",
        "date": "2026-09-26",
        "lane": "fo_v2_domain_question_a",
        "trigger": "T_V2_QUESTION_A",
        "kind": "owner_decision_brief",
        "decides_nothing": True,
        "chosen_option": None,
        "generated_by": SELF,
        "brief_md": BRIEF_MD,
        "v1_statement": audit["v1_statement"],
        "inputs": [dict(path=p, **{k: v for k, v in s.items()}) for p, s in INPUTS.items()],
        "question": question,
        "table_families": families,
        "ood_consequence": ood_consequence,
        "derived_bounds": derived,
        "completeness_reaudit": completeness,
        "options": options,
        "owner_decisions": owner_decisions,
        "cross_lane_checks": checks,
        "qa_observations": observations,
        "milestones": milestones,
    }


def dump(obj) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="rebuild and compare with the committed JSON")
    args = ap.parse_args(argv)
    text = dump(build())
    if args.check:
        with open(OUT, encoding="utf-8") as fh:
            same = fh.read() == text
        print("OK" if same else "DIFFERS")
        return 0 if same else 1
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
