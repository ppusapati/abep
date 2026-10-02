#!/usr/bin/env python3
"""Continuously updated architecture decision dossier (lane_27_decision_dossier) for hall_only / rf_hall / ecr_hall.

    python scripts/architecture/build_decision_dossier.py             # write docs/architecture_comparison/dossier/
    python scripts/architecture/build_decision_dossier.py --check     # exit 1 if the committed dossier is stale
    python scripts/architecture/build_decision_dossier.py --out-dir D # write elsewhere (tests)

What it does
------------
Assembles, from repository files only, the CURRENT STATUS of the architecture decision: per architecture the hard-gate
verdicts (PASS / FAIL / UNDETERMINED, with the evidence items used), whether it is eliminated (only via the hard-gate
logic, abep_sim/hard_gates.py), which decision milestone is reachable (A conditional with the explicit conditions list /
B / C) and what is missing for the next one, the measured / model-derived / assumed quantities the repository holds
(with their stated uncertainties and sources), the top unresolved failure-tree nodes and the next decisive evidence,
plus a provenance section (sha256 of every input file read, generation time, git commit).

Rules (lane contract; CLAUDE.md rules 3, 6, 10; docs/EVIDENCE.md)
-----------------------------------------------------------------
* Nothing is fabricated. Every value in the dossier is copied from an input file (path given) or counted from one.
  An input that is absent is listed as UNRESOLVED with the lane id that produces it; a present input that cannot be
  parsed as expected is listed as UNRESOLVED with the reason. There are no defaults.
* The dossier is a STATUS, not a decision. It never names a selected architecture unless the hard-gate logic has
  eliminated all architectures but one AND an owner decision record naming that architecture exists
  (OWNER_DECISION_RECORD). Architectures are always listed in fixed id order; nothing is ranked or scored.
* Screening candidates and unadmitted Hall closures are never performance sources. The dossier reports the admitted
  member set (abep_sim.hall_ensemble.member_ids(); empty today) and never reads a Hall map.
* Bundle 1 (docs/milestones/bundle1/, fo_bundle1_conditional_selection) is listed as an expected input; its outcome is
  never anticipated.
* Deterministic apart from provenance.generation.generated_at (set it with --generated-at or SOURCE_DATE_EPOCH).

Pure: reads files, imports abep_sim.hard_gates / abep_sim.hall_ensemble / abep_sim.arch_boundary (all in-repository,
pure), writes two files. Not wired into archengine; no simulation; goldens do not move.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
from typing import Any

CODE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if CODE_ROOT not in sys.path:
    sys.path.insert(0, CODE_ROOT)

DOSSIER_SCHEMA = "architecture_decision_dossier_v1"
LANE_ID = "lane_27_decision_dossier"
GENERATOR = "scripts/architecture/build_decision_dossier.py"
OUT_DIR_REL = "docs/architecture_comparison/dossier"
JSON_NAME = "dossier.json"
MD_NAME = "DECISION_DOSSIER.md"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
MILESTONE_ORDER = ("A", "B", "C")
OWNER_DECISION_RECORD = "docs/architecture_comparison/dossier/owner_decision_record.json"
TOP_NODES = 10
TOP_ACTIONS = 6

STATUS_STATEMENT = ("This dossier is a STATUS, not a decision. It records what the repository's evidence and gate logic "
                    "say today; no architecture is selected, ranked or scored. A selection can only be recorded by the "
                    "owner, and the dossier reports one only if the hard-gate logic has eliminated all but one "
                    "architecture and an owner decision record names that architecture.")

# ---------------------------------------------------------------------------------------------------------------------
# Input manifest. 'files' are read (and hashed) when present; 'dirs' are expected directories of lanes not yet merged:
# every file found under them is hashed and listed (content not interpreted), otherwise the input is UNRESOLVED.
# ---------------------------------------------------------------------------------------------------------------------
INPUTS: list[dict] = [
    {"key": "hard_gates", "lane": "lane_24_hard_gates", "role": "hard-gate matrix, evidence register, status and evaluator",
     "files": ["abep_sim/hard_gates.py", "docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json",
               "docs/architecture_comparison/hard_gates/evidence_register_v1.json",
               "docs/architecture_comparison/hard_gates/hard_gate_status_v1.json",
               "docs/architecture_comparison/hard_gates/HARD_GATES.md",
               "schemas/architecture_comparison/hard_gates_v1.schema.json"]},
    {"key": "transport_ensemble", "lane": "physics track (hallthruster_bridge/ensemble)",
     "role": "admitted Hall transport members (credible set); screening candidates are never performance sources",
     "files": ["abep_sim/hall_ensemble.py", "hallthruster_bridge/ensemble/transport_ensemble_v0.json"]},
    {"key": "failure_trees", "lane": "lane_26_failure_tree", "role": "architecture failure trees and ranked next evidence",
     "files": ["docs/architecture_comparison/failure_tree/failure_trees_v1.json",
               "docs/architecture_comparison/failure_tree/FAILURE_TREES.md"]},
    {"key": "evidence_rf_source", "lane": "lane_07_rf_evidence", "role": "RF source evidence matrix",
     "files": ["docs/evidence/rf_source/rf_evidence_matrix.json", "docs/evidence/rf_source/RF_SOURCE_EVIDENCE.md"]},
    {"key": "evidence_ecr_source", "lane": "lane_08_ecr_evidence", "role": "ECR source evidence matrix",
     "files": ["docs/evidence/ecr_source/ecr_evidence_matrix.json", "docs/evidence/ecr_source/ECR_SOURCE_EVIDENCE.md"]},
    {"key": "evidence_hall_sustainment", "lane": "lane_09_hall_sustainment",
     "role": "Hall-only sustainment / ignition evidence matrix",
     "files": ["docs/evidence/hall_sustainment/hall_sustainment_matrix.json",
               "docs/evidence/hall_sustainment/HALL_SUSTAINMENT_EVIDENCE.md"]},
    {"key": "evidence_cathode", "lane": "lane_10_cathode_dossier", "role": "cathode evidence matrix",
     "dirs": ["docs/evidence/cathode"]},
    {"key": "evidence_wall_life", "lane": "lane_32_wall_life", "role": "wall-life evidence matrix",
     "dirs": ["docs/evidence/wall_life"]},
    {"key": "feed_envelope", "lane": "lane_16_feed_envelope", "role": "common delivered-feed envelope",
     "files": ["docs/architecture_comparison/feed_envelope/feed_envelope_v1.json",
               "docs/architecture_comparison/feed_envelope/FEED_ENVELOPE.md"]},
    {"key": "hall_reference", "lane": "lane_17_hall_reference", "role": "common Hall accelerator reference",
     "files": ["docs/architecture_comparison/hall_reference/hall_reference_v1.json",
               "docs/architecture_comparison/hall_reference/HALL_ACCELERATOR_REFERENCE.md"]},
    {"key": "comparison_grid", "lane": "lane_23_comparison_grid", "role": "common comparison grid",
     "files": ["docs/architecture_comparison/comparison_grid/comparison_grid_v1.json",
               "docs/architecture_comparison/comparison_grid/COMPARISON_GRID.md"]},
    {"key": "breakeven", "lane": "lane_28_break_even", "role": "break-even surfaces",
     "files": ["docs/architecture_comparison/breakeven/breakeven_surfaces_v1.json",
               "docs/architecture_comparison/breakeven/BREAKEVEN_SURFACES.md"]},
    {"key": "overlay_rf", "lane": "fo_rf_breakeven_overlay", "role": "RF evidence on the break-even surfaces",
     "files": ["docs/architecture_comparison/overlays/rf/overlay_rf_v1.json",
               "docs/architecture_comparison/overlays/rf/RF_BREAKEVEN_OVERLAY.md"]},
    {"key": "overlay_ecr", "lane": "fo_ecr_breakeven_overlay", "role": "ECR evidence on the break-even surfaces",
     "files": ["docs/architecture_comparison/overlays/ecr/overlay_ecr_v1.json",
               "docs/architecture_comparison/overlays/ecr/ECR_BREAKEVEN_OVERLAY.md"]},
    {"key": "overlay_hall_sustainment", "lane": "fo_hall_sustainment_envelope",
     "role": "Hall-only sustainment evidence on the feed envelope",
     "files": ["docs/architecture_comparison/overlays/hall_sustainment/hall_sustainment_envelope_v1.json",
               "docs/architecture_comparison/overlays/hall_sustainment/HALL_SUSTAINMENT_ENVELOPE.md"]},
    {"key": "interstage", "lane": "lane_18_interstage", "role": "interstage transport model",
     "files": ["docs/architecture_comparison/interstage/INTERSTAGE_MODEL.md", "abep_sim/interstage.py",
               "schemas/architecture_comparison/interstage_v1.schema.json"]},
    {"key": "electrical_closure", "lane": "lane_20_ppu_magnet", "role": "electrical closure evidence data",
     "files": ["docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json",
               "docs/architecture_comparison/electrical_closure/ELECTRICAL_CLOSURE.md"]},
    {"key": "bus_power_boundary", "lane": "lane_11_bus_boundary", "role": "bus_power_boundary_v1",
     "files": ["abep_sim/arch_boundary.py", "docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md",
               "schemas/architecture_comparison/bus_power_boundary_v1.json"]},
    {"key": "comparison_harness", "lane": "lane_12_arch_harness", "role": "architecture comparison harness",
     "files": ["abep_sim/arch_compare.py", "docs/architecture_comparison/harness/HARNESS.md"]},
    {"key": "mass_bom", "lane": "lane_21_mass_bom", "role": "mass BOM",
     "files": ["docs/architecture_comparison/mass_bom/mass_bom_v1.json",
               "docs/architecture_comparison/mass_bom/MASS_BOM.md"]},
    {"key": "thermal_life", "lane": "lane_15_thermal_life", "role": "thermal / life framework",
     "files": ["abep_sim/thermal_life.py", "docs/thermal_life/THERMAL_LIFE_FRAMEWORK.md",
               "schemas/thermal_life/inputs_v1.json", "schemas/thermal_life/limits_v1.json"]},
    {"key": "scaling", "lane": "lane_22_scaling", "role": "scaling / similarity audit",
     "files": ["docs/architecture_comparison/scaling/scaling_similarity.json",
               "docs/architecture_comparison/scaling/SCALING_SIMILARITY.md"]},
    {"key": "minimum_decisive_experiment", "lane": "lane_25_min_decisive_experiment",
     "role": "minimum decisive experiment (draft)",
     "files": ["docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json",
               "docs/architecture_comparison/minimum_decisive_experiment/MINIMUM_DECISIVE_EXPERIMENT_DRAFT.md"]},
    {"key": "cathode_integration", "lane": "lane_19_cathode_integration", "role": "cathode integration",
     "files": ["docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json",
               "docs/architecture_comparison/cathode_integration/cathode_integration_derived_v1.json",
               "docs/architecture_comparison/cathode_integration/CATHODE_INTEGRATION.md"]},
    {"key": "experiment_protocol", "lane": "lane_06_experiment_protocol", "role": "common-condition experiment protocol",
     "files": ["docs/architecture_comparison/experiment_protocol/protocol_draft.json",
               "docs/architecture_comparison/experiment_protocol/EXPERIMENT_PROTOCOL_DRAFT.md"]},
    {"key": "upstream_icd", "lane": "lane_33_upstream_icd", "role": "upstream ICD schemas", "dirs": ["schemas/interfaces"]},
    {"key": "ledgers", "lane": "lane_34_ledgers", "role": "mass / power / thermal ledgers", "dirs": ["schemas/ledgers"]},
    {"key": "hallmap_spec", "lane": "lane_35_hallmap_spec", "role": "design Hall-map specification",
     "dirs": ["docs/hallmap"]},
    {"key": "o_o2_audit", "lane": "lane_13_o_o2_audit", "role": "O / O2 chemistry audit", "dirs": ["docs/chemistry/o_o2"]},
    {"key": "bundle1", "lane": "fo_bundle1_conditional_selection",
     "role": "Bundle 1 conditional-selection outcome (expected; never anticipated)", "dirs": ["docs/milestones/bundle1"]},
    {"key": "owner_decision_record", "lane": "owner",
     "role": "owner decision record (only an owner-recorded decision can make the dossier name an architecture)",
     "files": [OWNER_DECISION_RECORD]},
    {"key": "claude_md", "lane": "project instructions", "role": "gate status table (Physics Baseline 1.0)",
     "files": ["CLAUDE.md"]},
    {"key": "p5_n2_v1", "lane": "physics track (P5-N2 v1 vacuum campaign)", "role": "P5-N2 v1 decision and release",
     "files": ["hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_decision.json",
               "hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json"]},
    {"key": "forensics_p5_n2_v1", "lane": "lane_02_ood_attribution / lane_03_scoreable_subset / lane_29_exb_physics",
     "role": "P5-N2 v1 non-gating forensics",
     "files": ["docs/forensics/p5_n2_v1/ood_attribution/ood_attribution.json",
               "docs/forensics/p5_n2_v1/scoreable_subset/scoreable_subset.json",
               "docs/forensics/p5_n2_v1/exb_physics/exb_physics.json"]},
    {"key": "v2_question_a", "lane": "fo_v2_domain_question_a", "role": "owner disposition of v2 Question A",
     "files": ["docs/v2/question_a/QUESTION_A_DISPOSITION.json"]},
]

# Files that must be present and parsed for a section; each maps to the input key that holds it.
F = {
    "matrix": "docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json",
    "register": "docs/architecture_comparison/hard_gates/evidence_register_v1.json",
    "status": "docs/architecture_comparison/hard_gates/hard_gate_status_v1.json",
    "ftree": "docs/architecture_comparison/failure_tree/failure_trees_v1.json",
    "rf": "docs/evidence/rf_source/rf_evidence_matrix.json",
    "ecr": "docs/evidence/ecr_source/ecr_evidence_matrix.json",
    "hsus": "docs/evidence/hall_sustainment/hall_sustainment_matrix.json",
    "elec": "docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json",
    "mass": "docs/architecture_comparison/mass_bom/mass_bom_v1.json",
    "ov_rf": "docs/architecture_comparison/overlays/rf/overlay_rf_v1.json",
    "ov_ecr": "docs/architecture_comparison/overlays/ecr/overlay_ecr_v1.json",
    "ov_hs": "docs/architecture_comparison/overlays/hall_sustainment/hall_sustainment_envelope_v1.json",
    "decision": "hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_decision.json",
    "release": "hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json",
    "qa": "docs/v2/question_a/QUESTION_A_DISPOSITION.json",
    "claude": "CLAUDE.md",
    "owner": OWNER_DECISION_RECORD,
    "ensemble": "hallthruster_bridge/ensemble/transport_ensemble_v0.json",
}


class Unresolved(Exception):
    """A section cannot be assembled from the files present; the message says why (never a fallback value)."""


# ---------------------------------------------------------------------------------------------------------------------
# File access with provenance
# ---------------------------------------------------------------------------------------------------------------------
class Reader:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.read: dict[str, str] = {}          # rel path -> sha256 of the bytes read

    def abs(self, rel: str) -> str:
        return os.path.join(self.root, rel)

    def exists(self, rel: str) -> bool:
        return os.path.isfile(self.abs(rel))

    def bytes(self, rel: str) -> bytes:
        with open(self.abs(rel), "rb") as f:
            b = f.read()
        self.read[rel] = hashlib.sha256(b).hexdigest()
        return b

    def json(self, rel: str) -> Any:
        if not self.exists(rel):
            raise Unresolved(f"{rel} is not present in this checkout")
        try:
            return json.loads(self.bytes(rel).decode("utf-8"))
        except ValueError as e:
            raise Unresolved(f"{rel} is not valid JSON: {e}") from e

    def text(self, rel: str) -> str:
        if not self.exists(rel):
            raise Unresolved(f"{rel} is not present in this checkout")
        return self.bytes(rel).decode("utf-8")


def _git(root: str, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout


def _merge_commits(root: str) -> dict[str, str]:
    """lane id -> most recent 'Merge verified <lane>' commit in this checkout's history (provenance only)."""
    log = _git(root, "log", "--format=%H %s")
    out: dict[str, str] = {}
    if not log:
        return out
    for line in log.splitlines():
        sha, _, subj = line.partition(" ")
        m = re.match(r"Merge verified ((?:lane|fo)_[A-Za-z0-9_]+)", subj)
        if m and m.group(1) not in out:
            out[m.group(1)] = sha
    return out


def resolve_inputs(rd: Reader, merges: dict[str, str]) -> list[dict]:
    rows = []
    for spec in INPUTS:
        row: dict[str, Any] = {"key": spec["key"], "lane": spec["lane"], "role": spec["role"]}
        lanes = re.findall(r"\b(?:lane_\d+_[a-z0-9_]+|fo_[a-z0-9_]+)\b", spec["lane"])
        row["merge_commits"] = {ln: merges[ln] for ln in lanes if ln in merges}
        if "files" in spec:
            present = [p for p in spec["files"] if rd.exists(p)]
            missing = [p for p in spec["files"] if not rd.exists(p)]
            for p in present:
                rd.bytes(p)
            row["files"] = present
            row["missing_files"] = missing
            row["state"] = "PRESENT" if not missing else ("PARTIAL" if present else "UNRESOLVED")
        else:
            found = []
            for d in spec["dirs"]:
                base = rd.abs(d)
                if os.path.isdir(base):
                    for dp, dns, fns in os.walk(base):
                        # bytecode caches are interpreter by-products, not inputs: fingerprinting them made the
                        # dossier depend on which builders happened to have been imported in this checkout
                        dns[:] = sorted(x for x in dns if x != "__pycache__")
                        for fn in sorted(fns):
                            if fn.endswith((".pyc", ".pyo")):
                                continue
                            rel = os.path.relpath(os.path.join(dp, fn), rd.root).replace(os.sep, "/")
                            rd.bytes(rel)
                            found.append(rel)
            row["expected_dirs"] = spec["dirs"]
            row["files"] = found
            row["missing_files"] = [] if found else list(spec["dirs"])
            row["state"] = "PRESENT_NOT_INTERPRETED" if found else "UNRESOLVED"
        if row["state"] in ("UNRESOLVED", "PARTIAL"):
            if spec["key"] == "bundle1":
                row["reason"] = ("pending: Bundle 1 (fo_bundle1_conditional_selection) is built in parallel and is not "
                                 "in this checkout; its outcome is not anticipated here")
            elif spec["key"] == "owner_decision_record":
                row["reason"] = "no owner decision has been recorded; the dossier is a status only"
            else:
                row["reason"] = (f"not present in this checkout: produced by {spec['lane']}, not yet verified/merged "
                                 "into this base")
        rows.append(row)
    return rows


def _sec(fn, *a, **k) -> dict:
    """Run a section builder; an Unresolved input turns the section into an explicit UNRESOLVED record."""
    try:
        return fn(*a, **k)
    except Unresolved as e:
        return {"state": "UNRESOLVED", "reason": str(e)}
    except (KeyError, TypeError, ValueError, IndexError) as e:
        return {"state": "UNRESOLVED", "reason": f"input did not have the expected structure: {type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------------------------------------------------
def hard_gate_section(rd: Reader) -> dict:
    """Live evaluation of the committed evidence register with abep_sim.hard_gates, checked against the committed
    status file (a mismatch is reported as STALE_COMMITTED_STATUS; the live evaluation is used)."""
    for k in ("matrix", "register", "status"):
        if not rd.exists(F[k]):
            raise Unresolved(f"{F[k]} is not present in this checkout (lane_24_hard_gates)")
    try:
        from abep_sim import hard_gates as hg
    except ImportError as e:
        raise Unresolved(f"abep_sim.hard_gates is not importable: {e}") from e
    rd.json(F["matrix"]), rd.json(F["register"])          # hash what the evaluator reads
    committed = rd.json(F["status"])
    live = hg.build_status(register_path=rd.abs(F["register"]), matrix_path=rd.abs(F["matrix"]))
    strip = lambda d: {k: v for k, v in d.items() if k != "provenance"}   # noqa: E731
    consistency = "CURRENT" if strip(live) == strip(committed) else "STALE_COMMITTED_STATUS"
    register = rd.json(F["register"])
    return {"state": "RESOLVED", "evaluation": live, "committed_status_consistency": consistency,
            "register_items": len(register.get("items", [])),
            "register_note": register.get("note"),
            "evaluated_with": "abep_sim.hard_gates.build_status(register, matrix) (live), compared with "
                              f"{F['status']}"}


def _gate_rows(ev: dict, arch: str, node_gate_map: dict) -> list[dict]:
    a = ev["architectures"][arch]
    rows = []
    for gid, g in a["gates"].items():
        crits = []
        for cid, c in sorted(g["criteria"].items()):
            crits.append({"criterion": cid, "requirement": f"{c['metric']} {c['comparator']} "
                          f"{'TBD' if c['threshold'] is None else c['threshold']} {c['unit']}",
                          "status": c["status"], "verdict": c["verdict"], "counts_for_fail": c["counts_for_fail"],
                          "evidence_used": c["evidence_used"], "missing_for_pass": c["missing_for_pass"],
                          "missing_for_fail": c["missing_for_fail"]})
        rows.append({"gate": gid, "title": g["title"], "status": g["status"], "binding": g["binding"],
                     "verdict": g["verdict"], "milestone": g["milestone"], "conflict": g["conflict"],
                     "evidence_items": g["evidence_used"], "criteria": crits,
                     "open_failure_tree_nodes": sorted(node_gate_map.get(arch, {}).get(gid, []))})
    return rows


def failure_tree_section(rd: Reader) -> dict:
    ft = rd.json(F["ftree"])
    gate_map = {g["id"]: g["matrix_gate_id"] for g in ft["hard_gates"]}
    actions = {a["id"]: a for a in ft["actions"]}
    ev_rank = {"supported": 0, "unknown": 1, "contradicted": 2}
    per_arch: dict[str, Any] = {}
    node_gate_map: dict[str, dict[str, list]] = {}
    for arch in ARCHITECTURES:
        nodes = [n for n in ft["nodes"] if arch in n["architectures"] and n["decision_state"] == "open"]
        counted = [n for n in nodes if not n.get("sub_cause_of") and not n.get("branch")]
        gm: dict[str, list] = {}
        for n in nodes:
            for g in n["decision_quantity"].get("gates", []):
                gm.setdefault(gate_map.get(g, g), []).append(n["id"])
        node_gate_map[arch] = gm
        order = sorted(counted, key=lambda n: (ev_rank.get(n["evidence_status"], 3),
                                               MILESTONE_ORDER.index(n["resolve_by_milestone"]),
                                               -len(n["decision_quantity"].get("gates", [])), n["id"]))
        top = [{"id": n["id"], "title": n["title"], "evidence_status": n["evidence_status"],
                "resolve_by_milestone": n["resolve_by_milestone"],
                "gates": [gate_map.get(g, g) for g in n["decision_quantity"].get("gates", [])],
                "threshold_status": n["decision_quantity"].get("threshold_status"),
                "requires_admitted_hall_closure": n["analysis_requires_admitted_hall_closure"],
                "cheapest_resolution": n.get("cheapest_resolution", []),
                "milestone_A_condition": n.get("milestone_A_condition")} for n in order[:TOP_NODES]]
        rne = ft["ranked_next_evidence"]["per_architecture"][arch]
        nxt = [{"rank": r["rank"], "action": r["action"], "kind": r["kind"],
                "title": actions.get(r["action"], {}).get("title"),
                "deliverable": actions.get(r["action"], {}).get("deliverable"),
                "nodes_decided": r["nodes_decided"], "gates_decided": [gate_map.get(g, g) for g in r["gates_decided"]],
                "n_contributes": r["n_contributes"]} for r in rne["ranked"][:TOP_ACTIONS]]
        per_arch[arch] = {
            "n_open_nodes": len(nodes), "n_counted_open_nodes": len(counted),
            "n_branch_nodes": sum(1 for n in nodes if n.get("branch")),
            "n_sub_cause_nodes": sum(1 for n in nodes if n.get("sub_cause_of")),
            "evidence_status_counts": {s: sum(1 for n in counted if n["evidence_status"] == s)
                                       for s in sorted({n["evidence_status"] for n in counted})},
            "top_unresolved_nodes": top,
            "milestone_A_conditions": [{"node": n["id"], "condition": n["milestone_A_condition"]}
                                       for n in sorted(counted, key=lambda n: n["id"]) if n.get("milestone_A_condition")],
            "next_decisive_evidence": nxt,
            "blocked_actions": rne.get("blocked", []),
        }
    return {"state": "RESOLVED", "version": ft.get("version"), "status": ft.get("status"),
            "ranking_rule": ft["ranking_rule"]["id"], "eliminations_recorded": len(ft.get("eliminations", [])),
            "to_reach_B": ft["milestones"]["to_reach_B"], "to_reach_C": ft["milestones"]["to_reach_C"],
            "top_node_order_rule": ("dossier presentation order (not a ranking of architectures): counted open nodes "
                                    "(no sub-cause, no design branch) sorted by evidence_status supported < unknown < "
                                    "contradicted, then resolve_by_milestone B < C, then more linked gates, then id"),
            "per_architecture": per_arch, "_node_gate_map": node_gate_map}


def _classes(entries: list, key: str = "evidence_class") -> dict:
    out: dict[str, int] = {}
    for e in entries:
        c = e.get(key) or "unstated"
        out[c] = out.get(c, 0) + 1
    return dict(sorted(out.items()))


def quantities_section(rd: Reader) -> dict:
    """Measured / model-derived / assumed quantities as the input files classify them. Values are copied, not computed."""
    out: dict[str, Any] = {"state": "RESOLVED", "per_architecture": {a: {} for a in ARCHITECTURES}, "notes": []}
    # Bus-power components from the electrical closure data, mapped with the boundary's component list.
    try:
        from abep_sim import arch_boundary as ab
        required = {a: list(ab.REQUIRED_COMPONENTS[a]) for a in ARCHITECTURES}
        bv = ab.BOUNDARY_VERSION
    except ImportError as e:
        required, bv = None, None
        out["notes"].append(f"abep_sim.arch_boundary not importable ({e}): bus-power component mapping UNRESOLVED")
    elec = _sec(rd.json, F["elec"]) if rd.exists(F["elec"]) else {"state": "UNRESOLVED",
                                                                   "reason": f"{F['elec']} not present"}
    for arch in ARCHITECTURES:
        q = out["per_architecture"][arch]
        if required is None or "components" not in elec:
            q["bus_power_components"] = {"state": "UNRESOLVED",
                                         "reason": elec.get("reason", "boundary component list unavailable")}
        else:
            comps = {}
            for c in required[arch]:
                cd = elec["components"].get(c)
                if cd is None:
                    comps[c] = {"state": "UNRESOLVED", "reason": f"component {c} absent from {F['elec']}"}
                    continue
                comps[c] = {"efficiency_status": cd.get("efficiency_status"),
                            "efficiency_evidence": cd.get("efficiency_evidence", []),
                            "evidence_class_counts": _classes(cd.get("entries", [])),
                            "entries": [{"id": e.get("id"), "quantity": e.get("quantity"),
                                         "evidence_class": e.get("evidence_class"), "value": e.get("value"),
                                         "units": e.get("units"), "uncertainty": e.get("uncertainty"),
                                         "sources": e.get("source_ids"), "locator": e.get("locator"),
                                         "role": e.get("role"), "tbd_requires": e.get("tbd_requires")}
                                        for e in cd.get("entries", [])]}
            q["bus_power_components"] = {"boundary_version": bv, "source": F["elec"], "components": comps,
                                         "note": "entries are literature / datasheet / derivation evidence on other "
                                                 "hardware or TBD records; none is a Vyovrinda measurement"}
    # Evidence matrices: counts by evidence class and by regime match, per architecture they bear on.
    def matrix_summary(key: str, getter) -> dict:
        if not rd.exists(F[key]):
            return {"state": "UNRESOLVED", "reason": f"{F[key]} not present"}
        m = rd.json(F[key])
        ents = m["entries"]
        return {"source": F[key], "n_entries": len(ents), "evidence_class_counts": _classes(ents),
                "regime_match_counts": getter(ents)}

    def regime(ents):
        out_ = {}
        for e in ents:
            r = str((e.get("applicability_to_abep") or {}).get("regime_match", "unstated"))
            out_[r] = out_.get(r, 0) + 1
        return dict(sorted(out_.items()))

    def direction(ents):
        out_ = {}
        for e in ents:
            r = str((e.get("implication") or {}).get("direction", "unstated"))
            out_[r] = out_.get(r, 0) + 1
        return dict(sorted(out_.items()))
    rf = _sec(matrix_summary, "rf", regime)
    ecr = _sec(matrix_summary, "ecr", regime)
    hs = _sec(matrix_summary, "hsus", direction)
    if "regime_match_counts" in hs:
        hs["direction_counts"] = hs.pop("regime_match_counts")
    for arch in ARCHITECTURES:
        q = out["per_architecture"][arch]
        q["evidence_matrices"] = {"hall_sustainment (common Hall stage)": hs}
        if arch == "rf_hall":
            q["evidence_matrices"]["rf_source"] = rf
        if arch == "ecr_hall":
            q["evidence_matrices"]["ecr_source"] = ecr
    # Mass: plausibility screen per architecture.
    if rd.exists(F["mass"]):
        mb = _sec(rd.json, F["mass"])
        for arch in ARCHITECTURES:
            try:
                ps = mb["plausibility_screen"]["architectures"][arch]
                out["per_architecture"][arch]["mass"] = {
                    "source": F["mass"], "screen_verdict": ps["verdict"], "n_items": ps["n_items"],
                    "items_with_sourced_lower_bound": ps["items_with_lower_bound"],
                    "n_items_without_lower_bound": len(ps["items_without_lower_bound"]),
                    "g3_fail_evidence": ps["g3_fail_evidence"],
                    "strict_rollup": mb["rollups"][arch]["strict"]["status"]}
            except (KeyError, TypeError) as e:
                out["per_architecture"][arch]["mass"] = {"state": "UNRESOLVED", "reason": f"unexpected structure: {e}"}
    else:
        for arch in ARCHITECTURES:
            out["per_architecture"][arch]["mass"] = {"state": "UNRESOLVED", "reason": f"{F['mass']} not present"}
    return out


def milestone_a_extra(rd: Reader) -> dict:
    """Architecture-specific milestone-A condition statements published by the overlays (copied verbatim)."""
    out: dict[str, Any] = {}
    if rd.exists(F["ov_rf"]):
        s = rd.json(F["ov_rf"]).get("milestone_A_statement", {})
        out["rf_hall"] = {"source": F["ov_rf"], "conditions": s.get("conditions_for_rf_hall_as_baseline", [])}
    else:
        out["rf_hall"] = {"state": "UNRESOLVED", "reason": f"{F['ov_rf']} not present (fo_rf_breakeven_overlay)"}
    if rd.exists(F["ov_ecr"]):
        s = rd.json(F["ov_ecr"]).get("milestone_A_statement", {})
        out["ecr_hall"] = {"source": F["ov_ecr"], "conditions": [s["condition_set_for_milestone_A"]]
                           if s.get("condition_set_for_milestone_A") else [],
                           "stated_analysis_conditions": s.get("explicit_conditions", [])}
    else:
        out["ecr_hall"] = {"state": "UNRESOLVED", "reason": f"{F['ov_ecr']} not present (fo_ecr_breakeven_overlay)"}
    if rd.exists(F["ov_hs"]):
        hs = rd.json(F["ov_hs"])
        out["hall_only"] = {"source": F["ov_hs"],
                            "conditions": [f"{c['id']}: {c['condition']} [state: {c.get('state')}]"
                                           for c in hs.get("milestone_A_conditions", [])],
                            "note": "Hall-stage sustainment conditions; the Hall stage is common to all three "
                                    "architectures, the overlay is registered for hall_only"}
    else:
        out["hall_only"] = {"state": "UNRESOLVED", "reason": f"{F['ov_hs']} not present (fo_hall_sustainment_envelope)"}
    return out


def physics_track_section(rd: Reader) -> dict:
    out: dict[str, Any] = {"state": "RESOLVED"}
    text = rd.text(F["claude"])
    rows = re.findall(r"^\|\s*(\d)\s+([^|]+?)\s*\|\s*(.+?)\s*\|\s*$", text, flags=re.M)
    if not rows:
        raise Unresolved("CLAUDE.md gate-status table not found")
    out["claude_md_gate_status"] = [{"gate": int(n), "name": name, "status": st} for n, name, st in rows]
    dec = _sec(rd.json, F["decision"])
    out["p5_n2_v1_decision"] = dec if dec.get("state") == "UNRESOLVED" else {
        "source": F["decision"], "admission_mode": dec.get("admission_mode"), "promotable": dec.get("promotable"),
        "inconclusive": dec.get("inconclusive"), "failed_validation": dec.get("failed_validation")}
    rel = _sec(rd.json, F["release"])
    out["validation_release_v1"] = rel if rel.get("state") == "UNRESOLVED" else {
        "source": F["release"], "campaign": rel.get("campaign"), "decision": rel.get("decision"),
        "admission_records": rel.get("admission_records")}
    try:
        from abep_sim import hall_ensemble as he
        out["admitted_members"] = sorted(he.member_ids())
        out["admitted_members_source"] = "abep_sim.hall_ensemble.member_ids() (" + F["ensemble"] + ")"
    except Exception as e:                                   # noqa: BLE001 - reported, never defaulted
        out["admitted_members"] = None
        out["admitted_members_source"] = f"UNRESOLVED: {type(e).__name__}: {e}"
    qa = _sec(rd.json, F["qa"])
    out["v2_question_a"] = qa if qa.get("state") == "UNRESOLVED" else {
        "source": F["qa"], "decision": qa.get("decision"), "domain_path": qa.get("domain_path"),
        "reopening_condition": qa.get("reopening_condition")}
    fr = []
    for p in ("docs/forensics/p5_n2_v1/ood_attribution/ood_attribution.json",
              "docs/forensics/p5_n2_v1/scoreable_subset/scoreable_subset.json",
              "docs/forensics/p5_n2_v1/exb_physics/exb_physics.json"):
        if rd.exists(p):
            d = rd.json(p)
            fr.append({"source": p, "id": d.get("id"), "gating": False,
                       "role": d.get("role") or d.get("statement")})
        else:
            fr.append({"source": p, "state": "UNRESOLVED", "reason": "not present"})
    out["forensics"] = fr
    return out


def owner_record(rd: Reader) -> dict:
    if not rd.exists(F["owner"]):
        return {"state": "UNRESOLVED", "path": F["owner"], "reason": "no owner decision recorded"}
    d = rd.json(F["owner"])
    return {"state": "PRESENT", "path": F["owner"], "decided_by": d.get("decided_by"),
            "architecture": d.get("architecture"), "milestone": d.get("milestone"), "record": d}


# ---------------------------------------------------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------------------------------------------------
def build(root: str = CODE_ROOT, generated_at: str | None = None) -> dict:
    root = os.path.abspath(root)
    rd = Reader(root)
    merges = _merge_commits(root)
    inputs = resolve_inputs(rd, merges)
    hg_sec = _sec(hard_gate_section, rd)
    ft_sec = _sec(failure_tree_section, rd)
    q_sec = _sec(quantities_section, rd)
    a_extra = _sec(milestone_a_extra, rd)
    phys = _sec(physics_track_section, rd)
    owner = _sec(owner_record, rd)
    node_gate_map = ft_sec.pop("_node_gate_map", {}) if isinstance(ft_sec, dict) else {}
    unresolved_inputs = [{"key": r["key"], "lane": r["lane"], "state": r["state"], "missing": r["missing_files"],
                          "reason": r.get("reason")} for r in inputs if r["state"] in ("UNRESOLVED", "PARTIAL")]
    missing_lanes = sorted({r["lane"] for r in inputs if r["state"] in ("UNRESOLVED", "PARTIAL")
                            and r["key"] not in ("owner_decision_record",)})

    per_arch: dict[str, Any] = {}
    ev = hg_sec.get("evaluation") if hg_sec.get("state") == "RESOLVED" else None
    for arch in ARCHITECTURES:
        a: dict[str, Any] = {"architecture": arch}
        if ev is None:
            a["hard_gates"] = {"state": "UNRESOLVED", "reason": hg_sec.get("reason")}
            a["eliminated"] = None
            a["elimination_basis"] = "UNRESOLVED: hard-gate logic unavailable; nothing can be eliminated"
            a["milestones"] = {"state": "UNRESOLVED", "reason": hg_sec.get("reason")}
        else:
            r = ev["architectures"][arch]
            a["hard_gates"] = _gate_rows(ev, arch, node_gate_map)
            a["verdict_counts"] = {v: sum(1 for g in a["hard_gates"] if g["binding"] and g["verdict"] == v)
                                   for v in ("PASS", "FAIL", "UNDETERMINED")}
            a["proposed_gate_verdicts"] = {g["gate"]: g["verdict"] for g in a["hard_gates"] if not g["binding"]}
            a["eliminated"] = r["eliminated"]
            a["elimination_basis"] = r["elimination_basis"]
            a["proposed_gate_failures"] = r["proposed_gate_failures"]
            a["conflicts"] = r["conflicts"]
            mA, mB, mC = r["milestones"]["A"], r["milestones"]["B"], r["milestones"]["C"]
            if r["eliminated"]:
                reach = "NONE (eliminated by a binding hard gate)"
            elif mC["ready"]:
                reach = "C"
            elif mB["ready"]:
                reach = "B"
            elif mA["conditional_selection_available"]:
                reach = "A (conditional statement available from the gate logic; not an owner selection)"
            else:
                reach = "NONE (binding-gate evidence conflict to be resolved by the owner)"
            nxt = "C" if reach == "B" else ("B" if reach.startswith("A") else None)
            a["milestones"] = {
                "currently_reachable": reach,
                "next_milestone": nxt,
                "missing_for_next": (mB["missing"] if nxt == "B" else mC["missing"] if nxt == "C" else []),
                "A": {"conditional_selection_available": mA["conditional_selection_available"],
                      "statement": mA["statement"],
                      "hard_gate_conditions": [{"gate": c["gate"], "criterion": c["criterion"],
                                                "requirement": c["requirement"], "current_verdict": c["current_verdict"],
                                                "can_eliminate": c["can_eliminate"],
                                                "discharged_at_A_by": c["discharged_by"]["A"],
                                                "blockers": c["blockers"]} for c in mA["conditions"]],
                      "open_owner_items": [{"criterion": o["criterion"], "status": o["status"]}
                                           for o in mA["open_owner_items"]],
                      "proposed_gates_pending": mA["proposed_gates_pending"],
                      "failure_tree_conditions": (ft_sec["per_architecture"][arch]["milestone_A_conditions"]
                                                  if ft_sec.get("state") == "RESOLVED" else ft_sec),
                      "overlay_conditions": (a_extra.get(arch) if isinstance(a_extra, dict) else a_extra),
                      "formal_outcome": {"input": "docs/milestones/bundle1/ (fo_bundle1_conditional_selection)",
                                         "state": next(x["state"] for x in inputs if x["key"] == "bundle1"),
                                         "note": "the conditional-selection outcome is Bundle 1's; this dossier "
                                                 "does not anticipate it"}},
                "B": {"ready": mB["ready"], "missing": mB["missing"],
                      "failure_tree_to_reach_B": ft_sec.get("to_reach_B")},
                "C": {"ready": mC["ready"], "missing": mC["missing"],
                      "failure_tree_to_reach_C": ft_sec.get("to_reach_C"),
                      "missing_input_lanes": missing_lanes},
            }
        if ft_sec.get("state") == "RESOLVED":
            fa = ft_sec["per_architecture"][arch]
            a["failure_tree"] = {k: fa[k] for k in ("n_open_nodes", "n_counted_open_nodes", "n_branch_nodes",
                                                     "n_sub_cause_nodes", "evidence_status_counts",
                                                     "top_unresolved_nodes", "next_decisive_evidence",
                                                     "blocked_actions")}
        else:
            a["failure_tree"] = ft_sec
        a["quantities"] = (q_sec["per_architecture"][arch] if q_sec.get("state") == "RESOLVED" else q_sec)
        per_arch[arch] = a

    eliminated = [a for a in ARCHITECTURES if per_arch[a]["eliminated"] is True]
    not_eliminated = [a for a in ARCHITECTURES if per_arch[a]["eliminated"] is False]
    selected = None
    decision_status = "STATUS_NOT_A_DECISION"
    decision_note = STATUS_STATEMENT
    if owner.get("state") == "PRESENT":
        if (ev is not None and len(not_eliminated) == 1 and len(eliminated) == len(ARCHITECTURES) - 1
                and owner.get("architecture") == not_eliminated[0]):
            selected = not_eliminated[0]
            decision_status = "OWNER_DECISION_RECORDED"
            decision_note = (f"The hard-gate logic eliminates every architecture except {selected}, and the owner "
                             f"decision record ({F['owner']}) names it.")
        else:
            decision_note = (STATUS_STATEMENT + " An owner decision record exists, but the hard-gate logic has not "
                             "eliminated all architectures but the one it names, so the dossier does not report a "
                             "selection; see the record itself.")

    hg_summary = {k: v for k, v in hg_sec.items() if k != "evaluation"}
    if ev is not None:
        hg_summary.update({"matrix_version": ev["matrix_version"], "matrix_status": ev["matrix_status"],
                           "admitted_members": ev["admitted_members"], "eliminated": ev["eliminated"],
                           "not_eliminated": ev["not_eliminated"]})
    ft_summary = {k: v for k, v in ft_sec.items() if k != "per_architecture"}

    commit = (_git(root, "rev-parse", "HEAD") or "").strip() or "UNAVAILABLE"
    read_paths = sorted(rd.read)
    dirty = _git(root, "status", "--porcelain", "--", *read_paths) if read_paths else ""
    code_files = ["scripts/architecture/build_decision_dossier.py"]
    code_hashes = {}
    for p in code_files:
        with open(os.path.join(CODE_ROOT, p), "rb") as f:
            code_hashes[p] = hashlib.sha256(f.read()).hexdigest()
    if generated_at is None:
        sde = os.environ.get("SOURCE_DATE_EPOCH")
        t = (_dt.datetime.fromtimestamp(int(sde), _dt.timezone.utc) if sde
             else _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0))
        generated_at = t.isoformat().replace("+00:00", "Z")

    return {
        "schema": DOSSIER_SCHEMA,
        "lane": LANE_ID,
        "generator": GENERATOR,
        "nature": "STATUS_NOT_A_DECISION",
        "decision": {"decision_status": decision_status, "selected_architecture": selected,
                     "statement": decision_note, "eliminated": eliminated, "not_eliminated": not_eliminated,
                     "elimination_rule": "only a binding hard gate FAIL on sufficient evidence "
                                         "(abep_sim/hard_gates.py) eliminates an architecture",
                     "architecture_order": "fixed id order hall_only, rf_hall, ecr_hall; not a ranking",
                     "owner_decision_record": {k: v for k, v in owner.items() if k != "record"}},
        "milestone_definitions": {
            "A": "conditional selection: 'architecture X is baseline provided conditions ... are demonstrated'; does "
                 "not require Physics Baseline 1.0",
            "B": "physics-backed selection: credible envelopes from validated Hall transport, chemistry and "
                 "common-boundary performance",
            "C": "proposal/PDR freeze: mass, power, thermal, life, startup, cathode, mission closure integrated"},
        "dossier_supports_milestones": {
            "supports": ["A", "B", "C"],
            "how": "status tracking for all three milestones; it decides none of them",
            "to_reach_next": "A formal conditional selection needs Bundle 1 and an owner decision; B needs an admitted "
                             "Hall closure (credible set non-empty, O4 dispositions complete) or Vyovrinda hardware "
                             "measurements on every binding gate; C needs the integrated mass/power/thermal/life/"
                             "startup/cathode/mission closure (see per-architecture 'missing')"},
        "architectures": per_arch,
        "hard_gate_logic": hg_summary,
        "failure_trees": ft_summary,
        "quantity_notes": q_sec.get("notes", []) if q_sec.get("state") == "RESOLVED" else [q_sec.get("reason")],
        "physics_track": phys,
        "unresolved_inputs": unresolved_inputs,
        "inputs": inputs,
        "provenance": {
            "input_files_sha256": {p: rd.read[p] for p in read_paths},
            "generator_sha256": code_hashes,
            "git_commit": commit,
            "inputs_match_git_commit": (dirty == "") if dirty is not None else None,
            "generation": {"generated_at": generated_at},
            "deterministic_except": ["provenance.generation.generated_at"],
        },
    }


# ---------------------------------------------------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------------------------------------------------
def _v(x: Any, limit: int = 160) -> str:
    if x is None:
        return "—"
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, sort_keys=True)
    s = s.replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= limit else s[: limit - 1] + "…"


def render_md(d: dict) -> str:
    L: list[str] = []
    w = L.append
    w("# Architecture decision dossier (status, not a decision)")
    w("")
    w(f"Generated by `{d['generator']}` ({d['lane']}) at {d['provenance']['generation']['generated_at']} from git "
      f"commit `{d['provenance']['git_commit']}`. Regenerate with `python {d['generator']}`; "
      f"`--check` reports a stale dossier. Machine-readable twin: `dossier.json`.")
    w("")
    w(f"> **{d['decision']['decision_status']}.** {d['decision']['statement']}")
    w("")
    w("Milestones: A = conditional selection; B = physics-backed selection; C = proposal/PDR freeze. This dossier "
      "supports all three as status tracking and decides none. " + d["dossier_supports_milestones"]["to_reach_next"] + ".")
    w("")
    w("## Summary (fixed id order; not a ranking)")
    w("")
    w("| architecture | eliminated | binding gates PASS / FAIL / UNDETERMINED | PROPOSED gates | reachable milestone "
      "| next | open failure-tree nodes (counted) |")
    w("|---|---|---|---|---|---|---|")
    for arch in ARCHITECTURES:
        a = d["architectures"][arch]
        vc = a.get("verdict_counts")
        vcs = f"{vc['PASS']} / {vc['FAIL']} / {vc['UNDETERMINED']}" if vc else "UNRESOLVED"
        ms = a["milestones"]
        ft = a["failure_tree"]
        w(f"| {arch} | {_v(a['eliminated'])} | {vcs} | {_v(a.get('proposed_gate_verdicts'))} | "
          f"{_v(ms.get('currently_reachable', ms.get('state')))} | {_v(ms.get('next_milestone'))} | "
          f"{_v(ft.get('n_open_nodes', ft.get('state')))} ({_v(ft.get('n_counted_open_nodes'))}) |")
    w("")
    hgl = d["hard_gate_logic"]
    if hgl.get("state") == "RESOLVED":
        w(f"Hard-gate matrix {hgl['matrix_version']} ({hgl['matrix_status']}); evidence register items: "
          f"{hgl['register_items']}; committed status file: {hgl['committed_status_consistency']}; admitted Hall "
          f"closures: {hgl['admitted_members'] or 'none (credible set empty)'}.")
    else:
        w(f"Hard-gate logic: UNRESOLVED — {hgl.get('reason')}")
    w("")
    w("## Unresolved inputs")
    w("")
    w("| input | producing lane | state | missing | reason |")
    w("|---|---|---|---|---|")
    for u in d["unresolved_inputs"]:
        w(f"| {u['key']} | {u['lane']} | {u['state']} | {_v(', '.join(u['missing']))} | {_v(u['reason'], 220)} |")
    w("")
    for arch in ARCHITECTURES:
        a = d["architectures"][arch]
        w(f"## {arch}")
        w("")
        w("### Hard-gate verdicts")
        w("")
        if isinstance(a["hard_gates"], dict):
            w(f"UNRESOLVED — {a['hard_gates'].get('reason')}")
        else:
            w("| gate | binding | verdict | evidence items | open failure-tree nodes | missing for PASS (per criterion) |")
            w("|---|---|---|---|---|---|")
            for g in a["hard_gates"]:
                miss = "; ".join(f"{c['criterion']}: {', '.join(c['missing_for_pass'])}" for c in g["criteria"])
                w(f"| {g['gate']} — {_v(g['title'], 80)} | {'yes' if g['binding'] else 'no (PROPOSED)'} | "
                  f"{g['verdict']} | {_v(', '.join(g['evidence_items']) or 'none')} | "
                  f"{_v(', '.join(g['open_failure_tree_nodes']) or '—', 120)} | {_v(miss, 200)} |")
            w("")
            w(f"Eliminated: **{a['eliminated']}** (basis: {_v(a['elimination_basis'] or 'no binding gate FAIL')}).")
        w("")
        ms = a["milestones"]
        w("### Milestones")
        w("")
        if ms.get("state") == "UNRESOLVED":
            w(f"UNRESOLVED — {ms.get('reason')}")
        else:
            w(f"Currently reachable: **{ms['currently_reachable']}**. Next: {ms['next_milestone']}.")
            w("")
            w(f"*A.* {ms['A']['statement']}")
            w("")
            w("Hard-gate conditions (each must be demonstrated; 'A by' lists the evidence bases that can discharge it "
              "at milestone A):")
            w("")
            for c in ms["A"]["hard_gate_conditions"]:
                bl = f" Blockers: {' / '.join(c['blockers'])}" if c["blockers"] else ""
                w(f"- `{c['criterion']}`: {c['requirement']} — now {c['current_verdict']}; A by "
                  f"{', '.join(c['discharged_at_A_by']) or '(none)'}.{bl}")
            ftc = ms["A"]["failure_tree_conditions"]
            if isinstance(ftc, list):
                w("")
                w(f"Failure-tree milestone-A conditions ({len(ftc)} counted open nodes):")
                w("")
                for c in ftc:
                    w(f"- {c['node']}: {c['condition']}")
            oc = ms["A"]["overlay_conditions"]
            if isinstance(oc, dict):
                w("")
                if oc.get("state") == "UNRESOLVED":
                    w(f"Overlay conditions: UNRESOLVED — {oc.get('reason')}")
                else:
                    w(f"Overlay conditions (`{oc['source']}`):")
                    w("")
                    for c in oc.get("conditions", []):
                        w(f"- {c}")
            fo = ms["A"]["formal_outcome"]
            w("")
            w(f"Formal conditional-selection outcome: {fo['input']} — **{fo['state']}** ({fo['note']}).")
            w("")
            w(f"*Missing for {ms['next_milestone']}:* " + "; ".join(ms["missing_for_next"]) + ".")
            w("")
            extra_c = [x for x in ms["C"]["missing"] if x not in ms["missing_for_next"]]
            w("*Missing for C (in addition):* " + ("; ".join(extra_c) or "nothing beyond the above") + ".")
            if ms["C"]["missing_input_lanes"]:
                w("")
                w("*Inputs not yet in this checkout (needed before C):* " + ", ".join(ms["C"]["missing_input_lanes"]) + ".")
        w("")
        ft = a["failure_tree"]
        w("### Top unresolved failure-tree nodes and next decisive evidence")
        w("")
        if ft.get("state") == "UNRESOLVED":
            w(f"UNRESOLVED — {ft.get('reason')}")
        else:
            w(f"Open nodes: {ft['n_open_nodes']} (counted {ft['n_counted_open_nodes']}, design-branch "
              f"{ft['n_branch_nodes']}, sub-cause {ft['n_sub_cause_nodes']}); counted by evidence status: "
              f"{_v(ft['evidence_status_counts'])}.")
            w("")
            w("| node | title | evidence status | resolve by | gates | needs admitted closure | cheapest resolution |")
            w("|---|---|---|---|---|---|---|")
            for n in ft["top_unresolved_nodes"]:
                w(f"| {n['id']} | {_v(n['title'], 90)} | {n['evidence_status']} | {n['resolve_by_milestone']} | "
                  f"{', '.join(n['gates'])} | {n['requires_admitted_hall_closure']} | "
                  f"{', '.join(n['cheapest_resolution'])} |")
            w("")
            w("Next decisive evidence (failure-tree ranking rule, per architecture):")
            w("")
            for r in ft["next_decisive_evidence"]:
                w(f"{r['rank']}. {r['action']} ({r['kind']}) — {r['title']}; decides {', '.join(r['nodes_decided']) or 'no node alone'}"
                  f"; contributes to {r['n_contributes']} node(s).")
            for b in ft["blocked_actions"]:
                w(f"- Blocked: {b['action']} — {'; '.join(b['blocked_by'])}.")
        w("")
        q = a["quantities"]
        w("### Measured / model-derived / assumed quantities (as classified by their source files)")
        w("")
        if q.get("state") == "UNRESOLVED":
            w(f"UNRESOLVED — {q.get('reason')}")
        else:
            w("No Vyovrinda hardware measurement exists in the repository and no Hall transport closure is admitted, "
              "so no absolute Hall performance number appears here. Entries below are published evidence on other "
              "hardware, derivations, or TBD records, each with the class, uncertainty and source its file states.")
            w("")
            bp = q.get("bus_power_components", {})
            if bp.get("state") == "UNRESOLVED":
                w(f"Bus-power components: UNRESOLVED — {bp.get('reason')}")
            else:
                w(f"Bus-power components ({bp['boundary_version']}, `{bp['source']}`):")
                w("")
                w("| component | efficiency status | entry | class | value | units | uncertainty | sources |")
                w("|---|---|---|---|---|---|---|---|")
                for cname, c in bp["components"].items():
                    if c.get("state") == "UNRESOLVED":
                        w(f"| {cname} | UNRESOLVED | — | — | — | — | {_v(c['reason'])} | — |")
                        continue
                    for e in c["entries"]:
                        w(f"| {cname} | {c['efficiency_status']} | {e['id']} | {e['evidence_class']} | "
                          f"{_v(e['value'], 90)} | {_v(e['units'], 30)} | {_v(e['uncertainty'], 120)} | "
                          f"{_v(', '.join(e['sources'] or []), 60)} |")
            w("")
            for name, m in q.get("evidence_matrices", {}).items():
                if m.get("state") == "UNRESOLVED":
                    w(f"- Evidence matrix {name}: UNRESOLVED — {m.get('reason')}")
                else:
                    extra = m.get("regime_match_counts") or m.get("direction_counts")
                    w(f"- Evidence matrix {name} (`{m['source']}`): {m['n_entries']} entries; by class "
                      f"{_v(m['evidence_class_counts'])}; {'regime match' if 'regime_match_counts' in m else 'direction'} "
                      f"{_v(extra, 1000)}.")
            ma = q.get("mass", {})
            if ma.get("state") == "UNRESOLVED":
                w(f"- Mass: UNRESOLVED — {ma.get('reason')}")
            else:
                w(f"- Mass (`{ma['source']}`): screen {ma['screen_verdict']}; {ma['n_items']} items, "
                  f"{ma['n_items_without_lower_bound']} without a sourced lower bound; strict roll-up "
                  f"{ma['strict_rollup']}; G3 FAIL evidence: {ma['g3_fail_evidence']}.")
        w("")
    ph = d["physics_track"]
    w("## Physics track (meets the architecture track only through an admitted Hall closure)")
    w("")
    if ph.get("state") == "UNRESOLVED":
        w(f"UNRESOLVED — {ph.get('reason')}")
    else:
        w("| gate (CLAUDE.md) | status |")
        w("|---|---|")
        for g in ph["claude_md_gate_status"]:
            w(f"| {g['gate']} {g['name']} | {_v(g['status'], 300)} |")
        w("")
        dec = ph["p5_n2_v1_decision"]
        if dec.get("state") == "UNRESOLVED":
            w(f"- P5-N2 v1 decision: UNRESOLVED — {dec.get('reason')}")
        else:
            w(f"- P5-N2 v1 decision (`{dec['source']}`, {dec['admission_mode']}): promotable {dec['promotable']}; "
              f"inconclusive {len(dec['inconclusive'] or [])}; failed validation {dec['failed_validation']}.")
        rel = ph["validation_release_v1"]
        if rel.get("state") == "UNRESOLVED":
            w(f"- VALIDATION_RELEASE_v1: UNRESOLVED — {rel.get('reason')}")
        else:
            w(f"- VALIDATION_RELEASE_v1 (`{rel['source']}`): admission records {rel['admission_records']}.")
        w(f"- Admitted Hall transport members: {ph['admitted_members']} ({ph['admitted_members_source']}).")
        qa = ph["v2_question_a"]
        if qa.get("state") == "UNRESOLVED":
            w(f"- v2 Question A: UNRESOLVED — {qa.get('reason')}")
        else:
            w(f"- v2 Question A (`{qa['source']}`): {qa['decision']}, domain path {qa['domain_path']}.")
        for f_ in ph["forensics"]:
            w(f"- Forensics `{f_['source']}` (non-gating): {_v(f_.get('role') or f_.get('reason'), 240)}")
    w("")
    w("## Provenance")
    w("")
    pv = d["provenance"]
    w(f"- git commit: `{pv['git_commit']}`; input files match that commit: {pv['inputs_match_git_commit']}")
    w(f"- generated at: {pv['generation']['generated_at']} (the only non-deterministic field)")
    w(f"- generator sha256: {', '.join(f'`{k}` {v}' for k, v in pv['generator_sha256'].items())}")
    w("")
    w("| input file | sha256 |")
    w("|---|---|")
    for p, h in pv["input_files_sha256"].items():
        w(f"| `{p}` | `{h}` |")
    w("")
    return "\n".join(L)


def dump_json(d: dict) -> str:
    return json.dumps(d, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def _without_generation(d: dict) -> dict:
    d = json.loads(json.dumps(d))
    d["provenance"].pop("generation", None)
    d["provenance"].pop("git_commit", None)
    d["provenance"].pop("inputs_match_git_commit", None)
    return d


def write(d: dict, out_dir: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    jp, mp = os.path.join(out_dir, JSON_NAME), os.path.join(out_dir, MD_NAME)
    with open(jp, "w", encoding="utf-8") as f:
        f.write(dump_json(d))
    with open(mp, "w", encoding="utf-8") as f:
        f.write(render_md(d))
    return jp, mp


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=CODE_ROOT, help="repository root to read inputs from (default: this repository)")
    ap.add_argument("--out-dir", default=None, help=f"output directory (default: <root>/{OUT_DIR_REL})")
    ap.add_argument("--generated-at", default=None, help="ISO-8601 UTC timestamp (default: SOURCE_DATE_EPOCH or now)")
    ap.add_argument("--check", action="store_true",
                    help="compare the committed dossier.json with a fresh build (ignoring generation time, commit)")
    a = ap.parse_args(argv)
    out_dir = a.out_dir or os.path.join(a.root, OUT_DIR_REL)
    d = build(a.root, a.generated_at)
    if a.check:
        jp = os.path.join(out_dir, JSON_NAME)
        if not os.path.isfile(jp):
            print(f"STALE: {jp} does not exist")
            return 1
        with open(jp, encoding="utf-8") as f:
            old = json.load(f)
        # the committed dossier's own files are inputs of nothing; compare everything but generation metadata
        if _without_generation(old) != _without_generation(d):
            print("STALE: the committed dossier differs from a fresh build; regenerate it")
            return 1
        print("CURRENT")
        return 0
    jp, mp = write(d, out_dir)
    print(f"wrote {jp}\nwrote {mp}\ndecision_status: {d['decision']['decision_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
