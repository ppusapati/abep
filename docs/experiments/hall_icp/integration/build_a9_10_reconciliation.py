#!/usr/bin/env python3
"""A9-10 reconciliation record (fo_a9_10_integration, trigger T_A9_10_INTEGRATION; owner step A9.1 section 9 step 3).

Deterministic builder of docs/experiments/hall_icp/integration/a9_10_reconciliation_v1.json and its companion
A9_10_RECONCILIATION.md. It does not change any deliverable itself: the A9-10 changes are declared in
a9_10_overlay.py (applied by each lane builder) and in the listed builder/module code changes. This builder

  1. lists every change by deliverable with its driver (A9.1 decision id / verified lane item / integration open item);
  2. machine-checks, leaf by leaf against the A9-10 base (``git show BASE``), that every changed leaf of every A9 JSON
     deliverable is explained by a declared change, a declared code scope or a sha256 pin cascade, and that every
     changed NUMBER is explained by a record flagged numeric (A9.1 decision or verified upstream value);
  3. verifies every copied value (``source``) against the upstream JSON;
  4. re-evaluates every remaining 'PENDING' (OQ-INT-03) with a precise reason code, builds the chain -> DQ-HI consumer
     table for the unmapped A9-04 ids (OQ-INT-01, PROPOSED), reconciles the A9-03 published-analog annex with the A9-05
     extraction (OQ-INT-04; A9-05 governs), classifies every interface demand between the A9 lanes (both directions);
  5. verifies that every immutable / historical file is byte-identical to the A9-10 base;
  6. records the A9.2 incorporation (owner decisions 2026-09-30): the ten verbatim statuses, the RF-matching
     supersession, the anode and coupled-thermal blockers, decision coverage, the recommended next lanes (not launched)
     and a scan proving that no status-like field of the A9 deliverables claims PASS / CLOSES / RESOLVED for them.

Usage:
    python docs/experiments/hall_icp/integration/build_a9_10_reconciliation.py          # write JSON + MD
    python docs/experiments/hall_icp/integration/build_a9_10_reconciliation.py --check  # exit 1 on drift / failure

Pure standard library; reads files and ``git show`` only; no network; not wired into archengine. No value here is a
prediction; no winner is declared; A9 stays OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
LANE_DIR = "docs/experiments/hall_icp/integration"
JSON_REL = LANE_DIR + "/a9_10_reconciliation_v1.json"
MD_REL = LANE_DIR + "/A9_10_RECONCILIATION.md"
SCRIPT_REL = LANE_DIR + "/build_a9_10_reconciliation.py"
TEST_REL = "tests/test_a9_10_reconciliation.py"
BASE = "ecdad06e30bc5d2f172e862e4bd4843e86332d42"
CONFIGURATIONS = ("hall_c1_reference", "hall_icp_neutralizer")
A9_STATUS = "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE"
XE_DIR = "docs/budgets/" + "xe" + "_ledger_a9/"
M16_V3 = "docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json"
OQ_V2 = "docs/budgets/owner_decisions/owner_questions_state_v2.json"

_spec = importlib.util.spec_from_file_location("a9_10_overlay", os.path.join(HERE, "a9_10_overlay.py"))
OV = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(OV)

AUTHORITY_PINS = [
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
     "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "A9 governing owner decision"),
    ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
     "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "owner answers 1-147 (cited by row)"),
    ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
     "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976", "owner decision pack 147 (verbatim)"),
    ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
     "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4",
     "A9.1 follow-up owner decisions (binding for A9-10; cited by decision id)"),
    ("docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md",
     "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e", "A9.1 verbatim"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json",
     "beec91f9eca3ca0257c5ee88dcd193c87481660b9368b65c6d10b3b3bdae23b4", "A4 (immutable, binding)"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
     "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621", "A5 (immutable, binding)"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
     "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180", "A6 (immutable, binding)"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
     "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925", "A7 execution model (immutable)"),
]
GOVERNANCE_NOT_PINNED = ["docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                         "docs/orchestration/trigger_ledger_v2.jsonl", "docs/orchestration/fired_triggers.jsonl",
                         "docs/orchestration/runtime_state.json"]

DELIVERABLES = [
    {"key": "A9-01", "lane": "fo_a9_01_hall_icp_prereg_framework", "json": OV.PRE,
     "md": "docs/experiments/hall_icp/prereg_framework/HALL_ICP_PREREG_FRAMEWORK.md",
     "builder": "docs/experiments/hall_icp/prereg_framework/build_hall_icp_prereg_framework.py", "check": ["--check"],
     "test": "tests/test_hall_icp_prereg_framework.py"},
    {"key": "A9-02", "lane": "fo_a9_02_bus_boundary_a9", "json": OV.DELIVERABLE_FILES["A9-02"],
     "md": "docs/architecture_comparison/power_boundary_a9/BUS_POWER_BOUNDARY_A9.md",
     "builder": "docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py", "check": ["--check"],
     "test": "tests/test_bus_boundary_a9.py",
     "extra": ["abep_sim/bus_boundary_a9.py", "schemas/interfaces/bus_power_boundary_a9_v1.json"]},
    {"key": "A9-03", "lane": "fo_a9_03_icp_neutralizer_icd", "json": OV.ICD,
     "md": "docs/interfaces/icp_neutralizer/ICP_NEUTRALIZER_ICD.md",
     "builder": "docs/interfaces/icp_neutralizer/build_icp_neutralizer_icd.py", "check": ["--check"],
     "test": "tests/test_icp_neutralizer_icd.py"},
    {"key": "A9-04", "lane": "fo_a9_04_hall_icp_uncertainty_budget", "json": OV.UB,
     "md": "docs/experiments/hall_icp/uncertainty_budget/HALL_ICP_UNCERTAINTY_BUDGET.md",
     "builder": "docs/experiments/hall_icp/uncertainty_budget/build_hall_icp_uncertainty_budget.py",
     "check": ["--check"], "test": "tests/test_hall_icp_uncertainty_budget.py"},
    {"key": "A9-05ev", "lane": "fo_a9_05_hall_icp_validation_inputs (part 1)", "json": OV.EV,
     "md": "docs/evidence/icp_neutralizer/ICP_NEUTRALIZER_EVIDENCE.md",
     "builder": "docs/evidence/icp_neutralizer/build_icp_neutralizer_evidence.py", "check": ["--check"],
     "test": "tests/test_hall_icp_validation_inputs.py"},
    {"key": "A9-05vi", "lane": "fo_a9_05_hall_icp_validation_inputs (part 2)",
     "json": OV.DELIVERABLE_FILES["A9-05vi"],
     "md": "docs/experiments/hall_icp/validation_inputs/HALL_ICP_VALIDATION_INPUTS.md",
     "builder": "docs/experiments/hall_icp/validation_inputs/build_hall_icp_validation_inputs.py", "check": ["--check"],
     "test": "tests/test_hall_icp_validation_inputs.py"},
    {"key": "A9-06", "lane": "fo_a9_06_mass_reconciliation", "json": OV.MASS_A9, "md": "docs/budgets/mass_a9/MASS_A9.md",
     "builder": "docs/budgets/mass_a9/build_mass_a9.py", "check": ["--check"], "test": "tests/test_mass_a9.py"},
    {"key": "A9-07", "lane": "fo_a9_07_h2_revisions", "json": OV.H2A9,
     "md": "docs/hardware/h2_a9_revisions/H2_A9_REVISIONS.md",
     "builder": "docs/hardware/h2_a9_revisions/build_h2_a9_revisions.py", "check": ["--check"],
     "test": "tests/test_h2_a9_revisions.py"},
    {"key": "A9-08", "lane": "fo_a9_08_" + "xe" + "_ledger_update", "json": OV.XE_A9_JSON, "md": XE_DIR + "XE_LEDGER_A9.md",
     "builder": XE_DIR + "build_" + "xe" + "_ledger_a9.py", "check": ["--check"],
     "test": "tests/test_" + "xe" + "_ledger_a9.py"},
    {"key": "A9-09", "lane": "fo_a9_09_rfq_packages", "json": OV.RFQ_A9, "md": "docs/procurement/rfq_a9/RFQ_A9.md",
     "builder": "docs/procurement/rfq_a9/build_rfq_a9.py", "check": ["--check"], "test": "tests/test_rfq_a9.py"},
]
INTEGRATION = {"json": LANE_DIR + "/a9_core_integration_v1.json", "md": LANE_DIR + "/A9_CORE_INTEGRATION.md",
               "builder": LANE_DIR + "/build_a9_core_integration.py", "test": "tests/test_a9_core_integration.py"}

# Immutable / historical files that must stay byte-identical to BASE (directories are expanded with git ls-tree).
IMMUTABLE_ROOTS = [
    ("docs/decisions", "owner decisions (A4..A9, A9.1, 147 answers)"),
    ("docs/hardware/h2", "H2 v1 deliverables (H2-1..H2-7)"),
    ("docs/budgets/" + "xe" + "_ledger", "Xe ledger v1"),
    ("docs/architecture_comparison/mass_bom", "mass BOM v1"),
    ("abep_sim/mass_bom.py", "mass BOM v1 module"),
    ("docs/budgets/subsystem_maturity/subsystem_maturity_v1.json", "M16 v1"),
    ("docs/budgets/subsystem_maturity/SUBSYSTEM_MATURITY.md", "M16 v1 document"),
    ("docs/budgets/subsystem_maturity/subsystem_maturity_v2.json", "M16 v2"),
    ("docs/budgets/subsystem_maturity/SUBSYSTEM_MATURITY_v2.md", "M16 v2 document"),
    ("docs/budgets/subsystem_maturity/build_subsystem_maturity.py", "M16 v2 builder"),
    ("docs/budgets/owner_decisions/OWNER_QUESTIONS_CONSOLIDATED.md", "v1 consolidated owner list"),
    ("docs/budgets/owner_decisions/owner_questions_consolidated.csv", "v1 consolidated owner list (csv)"),
    ("docs/budgets/owner_decisions/owner_questions_consolidated.xlsx", "v1 consolidated owner list (xlsx)"),
    ("docs/budgets/owner_decisions/build_owner_questions_consolidated.py", "v1 consolidated owner list builder"),
    ("docs/budgets/owner_decisions/owner_decision_register_v1.json", "owner decision register v1"),
    ("docs/budgets/owner_decisions/OWNER_DECISION_REGISTER.md", "owner decision register v1 document"),
    ("docs/interfaces/preionizer_module", "historical pre-ionizer module ICD"),
    ("schemas/interfaces/preionizer_module_icd_v1.json", "historical pre-ionizer module ICD schema"),
    ("docs/experiments/phase1_prereg_framework", "historical A5 Phase-1 prereg framework"),
    ("docs/architecture_comparison/lock1", "historical LOCK-1 drafts"),
    ("abep_sim/arch_boundary.py", "historical bus_power_boundary_v1 module"),
]

# ------------------------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------------------------
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "rb") as f:
        return sha256_bytes(f.read())


def git_show(rel: str, commit: str = BASE) -> bytes:
    r = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"git show {commit}:{rel} failed: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def git_ls(rel: str, commit: str = BASE) -> list:
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit, "--", rel], cwd=ROOT, capture_output=True,
                       text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git ls-tree {commit} {rel} failed: {r.stderr.strip()}")
    return [x for x in r.stdout.splitlines() if x]


def load(rel: str):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def load_base(rel: str):
    return json.loads(git_show(rel).decode("utf-8"))


def leaves(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, p + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, p + f"[{i}]")
    else:
        yield p, o


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "[")


def get_ptr(doc, ptr: str):
    locs = OV.resolve(doc, ptr)
    if len(locs) != 1:
        raise RuntimeError(f"pointer {ptr} resolves to {len(locs)} locations")
    _p, par, k = locs[0]
    return par[k]


# ------------------------------------------------------------------------------------------------------------------
# (1)+(2) changes and leaf-level verification
# ------------------------------------------------------------------------------------------------------------------
PIN_LEAF = re.compile(r"(sha256|_sha|pins|pinned_inputs|read_deliverables|deliverable_pins|decision_pins)")


def verify_deliverable(d: dict, recs: list, errors: list) -> dict:
    rel = d["json"]
    before, after = load_base(rel), load(rel)
    lb, la = dict(leaves(before)), dict(leaves(after))
    sec = after.get("a9_10_reconciliation")
    if not sec:
        errors.append(f"{rel}: no a9_10_reconciliation section")
        sec = {"changes": []}
    declared = [r["cid"] for r in recs]
    in_file = [c["cid"] for c in sec["changes"]]
    if sorted(declared) != sorted(in_file):
        errors.append(f"{rel}: changes in the file {sorted(in_file)} != declared {sorted(declared)}")
    counts = {c["cid"]: c["count"] for c in sec["changes"]}
    # concrete coverage from pointer ops (resolved on the current document)
    covered_exact, covered_prefix, gsubs, codes = set(), [], [], []
    for r in recs:
        if r["op"] == "code":
            codes.append(r)
            covered_prefix += [(s, r) for s in r["scope"]]
            continue
        if r["op"] == "gsub":
            gsubs.append(r)
            continue
        for path, _par, _k in OV.resolve(after, r["ptr"]):
            covered_prefix.append((path, r))
    covered_prefix.append(("/a9_10_reconciliation", {"cid": "A9-10 section", "numeric": True}))
    changed = []
    for p in sorted(set(lb) | set(la)):
        vb, va = lb.get(p, "<absent>"), la.get(p, "<absent>")
        if vb == va and type(vb) is type(va):
            continue
        changed.append((p, vb, va))
    unexplained, numeric_unexplained, by_kind = [], [], {"op": 0, "gsub": 0, "code": 0, "pin": 0, "section": 0}
    for p, vb, va in changed:
        numeric = is_num(vb) or is_num(va)
        hits = [(len(pre), r) for pre, r in covered_prefix if under(p, pre)]
        rec = max(hits, key=lambda t: t[0])[1] if hits else None       # most specific declared change wins
        kind = None
        if rec is not None:
            kind = "section" if rec["cid"] == "A9-10 section" else ("code" if rec.get("op") == "code" else "op")
        elif isinstance(vb, str) and isinstance(va, str):
            for g in gsubs:
                if (not g["ptr"] or under(p, g["ptr"])) and g["old"] in vb and g["new"] in va:
                    rec, kind = g, "gsub"
                    break
        if rec is None and PIN_LEAF.search(p) and (isinstance(va, str) or va == "<absent>"):
            rec, kind = {"cid": "pin cascade", "numeric": False}, "pin"
        if rec is None:
            unexplained.append(p)
            continue
        by_kind[kind] += 1
        if numeric and not rec.get("numeric") and kind != "section":
            numeric_unexplained.append(p)
    for p in unexplained[:20]:
        errors.append(f"{rel}{p}: changed leaf not explained by a declared A9-10 change")
    for p in numeric_unexplained[:20]:
        errors.append(f"{rel}{p}: changed NUMBER not explained by a numeric A9.1 / verified-upstream record")
    for r in recs:
        if r["op"] == "code":
            with open(os.path.join(ROOT, r["file"]), encoding="utf-8") as f:
                if r["marker"] not in f.read():
                    errors.append(f"{r['cid']}: code marker missing in {r['file']}")
        src = r.get("source")
        if src:
            got = get_ptr(load(src["file"]), src["ptr"])
            if got != src["value"]:
                errors.append(f"{r['cid']}: copied value {src['value']!r} != {src['file']}{src['ptr']} = {got!r}")
    return {"deliverable": d["key"], "file": rel, "changed_leaves": len(changed),
            "explained_by": by_kind, "unexplained": len(unexplained), "numeric_unexplained": len(numeric_unexplained),
            "numeric_leaves_changed": sum(1 for _p, vb, va in changed if is_num(vb) or is_num(va)),
            "changes": [dict(cid=r["cid"], driver=r["driver"], op=r["op"],
                             ptr=r["ptr"] if r["op"] != "code" else r["file"], count=counts.get(r["cid"]),
                             numeric=bool(r.get("numeric")), summary=r["summary"],
                             **({"scope": r["scope"]} if r["op"] == "code" else {}),
                             **({"source": r["source"]} if r.get("source") else {}))
                        for r in recs]}


# ------------------------------------------------------------------------------------------------------------------
# (4a) PENDING re-evaluation (OQ-INT-03)
# ------------------------------------------------------------------------------------------------------------------
REASONS = {
    "NOT_A_CROSS_REFERENCE": "status vocabulary / document status literal / form definition; not a reference to "
                             "another lane",
    "HISTORICAL_COPY": "verbatim copy of an H2 v1 status inside the A9-07 revision register ('old' side); historical "
                       "text is never rewritten; the revision is the REV entry's 'new' side",
    "H2_V1_REVISED_IN_A9_07": "the H2 v1 deliverable is immutable; its A9 revision is recorded in "
                              "docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json (A9-07), which revises the "
                              "requirement but gives no measured or design value for this item",
    "HISTORICAL_PREIONIZER": "historical pre-ionizer module ICD item (byte-identical, not used for the primary line)",
    "ASSIGNMENT_NOT_DEFINED_BY_TARGET": "A9-01 and A9-04 are merged, but neither defines the per-input producing "
                                        "stage / decision-quantity assignment; proposed for LOCK-1 as OQ-A910-02 "
                                        "(owner call)",
    "UNMAPPED_DQ_ID": "UNMAPPED A9-04 id: kept as a measurement-chain id; its DQ-HI consumers are listed in "
                      "dq_consumer_table (OQ-INT-01 PROPOSED, owner call)",
    "DEPENDS_ON_LOCK_OR_OWNER": "frozen only at LOCK-1 / LOCK-2 or by an owner decision; the target lane defines the "
                                "form only",
    "DEPENDS_ON_HARDWARE_OR_EVIDENCE": "needs hardware, a registered stand envelope, a selected device or a "
                                      "measurement; no lane can supply it",
    "TARGET_CHECKED_NOT_DEFINED": "checked against the merged target: it does not define this value (the precise "
                                  "detail is given per occurrence in 'detail')",
    "A9_08_OPEN_AFTER_A9_07": "the A9 Xe ledger item waits on vendor/design-qualified C1 values; A9-07 (merged) "
                              "revises requirements and gives none",
    "A9_08_OPEN_AFTER_A9_09": "the A9 Xe ledger item waits on quotations; A9-09 (merged) issued specifications only",
    "H2_4_SELECTION": "waits on the H2-4 PPU/supply selection (quotation stage, A9-09)",
}
PENDING_RULES = [
    # (deliverable regex, pointer regex, text regex, reason)
    (r".*", r".*", r"^(DRAFT_)?PENDING_OWNER|PENDING_OWNER_NOT_PREREGISTERED|PENDING <lane path>|^PENDING$|"
                   r"PENDING/PROPOSED|TBD/PENDING|TBD or PENDING", "NOT_A_CROSS_REFERENCE"),
    (r"A9-07", r"^/revision_register\[\d+\]/old/", r".*", "HISTORICAL_COPY"),
    (r".*", r".*", r"PENDING docs/interfaces/preionizer_module/", "HISTORICAL_PREIONIZER"),
    (r"A9-05vi", r".*", r"\(A9-01 stage map|\(A9-04 measurement chain / decision", "ASSIGNMENT_NOT_DEFINED_BY_TARGET"),
    (r"A9-04", r".*", r"decision-quantity id and role", "UNMAPPED_DQ_ID"),
    (r".*", r".*", r"PENDING docs/hardware/h2/", "H2_V1_REVISED_IN_A9_07"),
    (r".*", r".*", r"LOCK-2 numbers|margin value|gate definition|contrast|if used, S1b|list PENDING|"
                   r"PENDING A9-01 preregistration|criteria PENDING|basis PENDING", "DEPENDS_ON_LOCK_OR_OWNER"),
    (r".*", r".*", r"hardware not built|P_d,max|I_d,max|HW-MC-13|supply rating|device selection|"
                   r"discharge slot limit", "DEPENDS_ON_HARDWARE_OR_EVIDENCE"),
    (r".*", r".*", r"PENDING H2-4", "H2_4_SELECTION"),
    (r".*", r".*", r"module masses PENDING H2-7 / module design|flight value PENDING",
     "DEPENDS_ON_HARDWARE_OR_EVIDENCE"),
    (r"A9-01", r"/interface_demands", r"ICP channels PENDING", "TARGET_MERGED_DOES_NOT_DEFINE"),
    (r"A9-08", r".*", r"PENDING A9-07", "A9_08_OPEN_AFTER_A9_07"),
    (r"A9-08", r".*", r"PENDING A9-09", "A9_08_OPEN_AFTER_A9_09"),
    # No catch-all: every remaining 'PENDING <A9 lane>' is either filled / re-stated by an overlay record (the
    # review repair, a9_10_overlay._repair) or listed individually in PRECISE_REMAINING with the checked reason.
]
# (deliverable, pointer) -> (reason code, precise detail checked against the target content). Every entry was
# checked against the merged target; an entry whose pointer no longer reads PENDING fails the build (stale entry).
PRECISE_REMAINING = {}


def classify_pending(key: str, ptr: str, frag: str, full: str):
    if (key, ptr) in PRECISE_REMAINING:
        return PRECISE_REMAINING[(key, ptr)][0]
    for dk, pk, tk, reason in PENDING_RULES:
        if re.fullmatch(dk, key) and re.search(pk, ptr) and (re.search(tk, frag) or re.search(tk, full)):
            return reason
    return None


def pending_occurrences(doc) -> list:
    out = []
    for p, v in leaves(doc):
        if isinstance(v, str) and "PENDING" in v:
            for m in re.finditer("PENDING", v):
                out.append((p, v[max(0, m.start() - 20):m.start() + 140], v))
    return out


def pending_reevaluation(errors: list) -> dict:
    per, remaining = [], []
    for d in DELIVERABLES:
        doc = load(d["json"])
        doc = {k: v for k, v in doc.items() if k != "a9_10_reconciliation"}
        base = load_base(d["json"])
        occ_b, occ_a = pending_occurrences(base), pending_occurrences(doc)
        for p, frag, full in occ_a:
            reason = classify_pending(d["key"], p, frag, full)
            if reason is None:
                errors.append(f"unclassified remaining PENDING {d['json']}{p}: {frag[:80]}")
                continue
            row = {"deliverable": d["key"], "pointer": p, "text": frag, "reason": reason}
            if (d["key"], p) in PRECISE_REMAINING:
                row["detail"] = PRECISE_REMAINING[(d["key"], p)][1]
            remaining.append(row)
        pb = {p for p, _f, _v in occ_b}
        pa = {p for p, _f, _v in occ_a}
        for (k, ptr) in PRECISE_REMAINING:
            if k == d["key"] and ptr not in pa:
                errors.append(f"stale PRECISE_REMAINING entry {k}{ptr} (no PENDING there any more)")
        per.append({"deliverable": d["key"], "file": d["json"], "pending_at_base": len(occ_b),
                    "pending_now": len(occ_a), "leaves_no_longer_pending": len(pb - pa),
                    "leaves_pending_at_base": len(pb)})
    return {"rule": "every 'PENDING' still present is re-evaluated against the now-merged lanes: filled or re-stated "
                    "where the target (or an A9.1 decision) gives the value (overlay records A910-R*, driver OQ-INT-03, "
                    "see changes_by_deliverable), otherwise kept with a reason code (reason_codes) and, where the "
                    "code is TARGET_CHECKED_NOT_DEFINED, the per-occurrence detail of what the target does and does "
                    "not define; there is no catch-all rule: an unclassified occurrence fails the build",
            "reason_codes": REASONS, "per_deliverable": per,
            "remaining_by_reason": {k: sum(1 for x in remaining if x["reason"] == k) for k in REASONS},
            "remaining": remaining}


# ------------------------------------------------------------------------------------------------------------------
# (4b) chain -> DQ-HI consumer table (OQ-INT-01, PROPOSED)
# ------------------------------------------------------------------------------------------------------------------
def dq_consumer_table(errors: list) -> dict:
    ub, pre = load(OV.UB), load(OV.PRE)
    integ = load(INTEGRATION["json"])
    decl = {r["ub_dq_id"]: r for r in integ["dq_id_mapping"]["rows"]}
    dqs = {q["id"]: q for q in pre["decision_quantities"]}
    chains = {c["dq"]: c for c in ub["measurement_chains"]}
    rows = []
    for r in ub["dq_id_mapping"]["rows"]:
        if r["dq_hi_id"]:
            continue
        uid = r["ub_dq_id"]
        ch = chains.get(uid)
        if ch is None:
            errors.append(f"no A9-04 measurement chain for {uid}")
            continue
        declared = sorted({m for c in decl[uid]["a9_01_consumers_not_counterparts"]
                           for m in re.findall(r"DQ-HI-[A-Z]+", c)})
        for q in declared:
            if q not in dqs:
                errors.append(f"consumer {q} of {uid} is not an A9-01 decision quantity")
        ins = [m.group(0) for i in ch["instruments"] for m in [re.search(r"INS-\d\d", i)] if m]
        primary = ins[0] if ins else None
        overlap = sorted(q for q, v in dqs.items()
                         if primary and any(c.split()[0] == primary for c in v["measurement_chain"]))
        rows.append({"ub_dq_id": uid, "symbols": r["ub_definition"], "chain_instruments": ch["instruments"],
                     "primary_ins": primary, "dq_hi_consumers_declared": declared,
                     "dq_hi_sharing_primary_instrument": overlap,
                     "proposed_resolution": "keep " + uid + " as a measurement-chain id (no DQ-HI id invented); its "
                                            "uncertainty feeds the listed DQ-HI consumers; owner call (OQ-INT-01)",
                     "status": "PROPOSED"})
    feeds = {}
    for row in rows:
        for q in row["dq_hi_consumers_declared"]:
            feeds.setdefault(q, []).append(row["ub_dq_id"])
    return {"question": "OQ-INT-01", "status": "PROPOSED (owner call; ids kept)",
            "rule": "declared consumers = the A9-01 quantities named in the step-1 mapping rows "
                    "(a9_01_consumers_not_counterparts); instrument overlap = A9-01 quantities whose measurement chain "
                    "contains the chain's primary INS id (informational)",
            "rows": rows, "dq_hi_fed_by": {k: sorted(v) for k, v in sorted(feeds.items())}}


# ------------------------------------------------------------------------------------------------------------------
# (4c) A9-03 annex vs A9-05 extraction (OQ-INT-04; A9-05 governs)
# ------------------------------------------------------------------------------------------------------------------
ANNEX_MAP = [
    ("TAK-01", ["TK-32", "TK-33"], "consistent (1 m x 2 m chamber, three TMP systems, base 1e-4 Pa); A9-03 keeps them "
     "as numbers, A9-05 as reported text + Pa value"),
    ("TAK-02", ["TK-10"], "consistent (65 mm pyrex tube); A9-05 locator adds p. 6 text"),
    ("TAK-03", ["TK-11"], "consistent (insulated, grounded antenna shield); A9-05 adds the double-turn loop antenna"),
    ("TAK-04", ["TK-20", "TK-21", "TK-22", "TK-23"], "consistent (13.56 MHz, 200 W, no reflection); A9-03 'none "
     "detected' vs A9-05 value 0 W"),
    ("TAK-05", ["TK-30", "TK-31", "TK-34"], "consistent (Ar only, 70 sccm = 2.1 mg/s, about 28 mPa)"),
    ("TAK-06", ["TK-40"], "consistent (isolation transformer, 50 ohm series resistor, 13.56 MHz L-C circuit)"),
    ("TAK-07", ["TK-13"], "consistent (C-type stainless electrode, 10 cm)"),
    ("TAK-08", ["TK-50", "TK-51"], "value consistent (V_D > 140 V; none without RF); LOCATOR differs: A9-03 cites "
     "Fig. 4a on p. 7, A9-05 p. 3 / p. 6 text -> A9-05 governs"),
    ("TAK-09", ["TK-03"], "consistent (0.1-0.15 T at z ~ -10 mm, authors' calculation = model-derived)"),
    ("TAK-10", ["TK-55", "TK-70"], "consistent (V_K to about -100 V; ~140 / ~220 V ion energies); A9-05 classes the "
     "ion energies 'inferred'"),
    ("TAK-11", ["TK-71"], "A9-05 is more complete: films on the glass tube at the electrode slit and on the HET-front "
     "insulators; A9-03 locator 'Fig. 5 (illustration) on p. 8' vs A9-05 'Fig. 5' -> A9-05 governs"),
    ("TAK-12", ["TK-24", "TK-25", "TK-26", "TK-27"], "values consistent (0.36 / 0.4 ohm, 0.1, 20 W); EVIDENCE CLASS "
     "differs: A9-03 'inferred (from measured resistances)' for the whole entry, A9-05 measured for R_ant / R_total, "
     "inferred for eta_p and value_basis authors_estimate for the 20 W; locator p. 8 vs p. 7-8 -> A9-05 governs"),
    ("TAK-13", ["TK-52", "TK-53"], "consistent (I_D about 1 A; limit attributed by the authors to the RF power); "
     "A9-03 locator 'p. 7 Fig. 4b' vs A9-05 'Fig. 4b' -> A9-05 governs"),
    ("TAK-14", ["TK-57"], "consistent (RFEA at z = 25 cm, 10 mm orifice)"),
]


def annex_reconciliation(errors: list) -> dict:
    icd, ev = load(OV.ICD), load(OV.EV)
    tak = {e["id"]: e for e in icd["published_analog_annex"]["entries"]}
    tk = {e["id"]: e for e in ev["extraction"]}
    if sorted(tak) != sorted(t for t, _k, _n in ANNEX_MAP):
        errors.append(f"annex entries {sorted(tak)} not all reconciled")
    rows = []
    for t, ks, note in ANNEX_MAP:
        a = tak[t]
        for k in ks:
            if k not in tk:
                errors.append(f"A9-05 extraction id {k} missing")
        rows.append({"a9_03_id": t, "a9_03_quantity": a["quantity"], "a9_03_value": a["value"],
                     "a9_03_locator": a["locator"], "a9_03_evidence_class": a["evidence_class"],
                     "a9_05_ids": ks,
                     "a9_05": [{"id": k, "quantity": tk[k]["quantity"], "value": tk[k].get("value"),
                                "unit": tk[k].get("unit"), "locator": tk[k].get("locator"),
                                "epistemic": tk[k].get("epistemic"), "evidence_class": tk[k].get("evidence_class")}
                               for k in ks if k in tk],
                     "difference": note, "governs": "A9-05"})
    return {"question": "OQ-INT-04", "rule": "A9-05 (" + OV.EV + ") owns the authoritative extraction; where the A9-03 "
            "annex differs in value, locator or evidence class, A9-05 governs; both are 'published analog, reported' "
            "context only, never Vyovrinda performance", "source": "Takahashi, Watanabe, Nakahama, Kikuchi, J. Electr. "
            "Propuls. 3:18 (2024), DOI 10.1007/s44205-024-00081-2 (CC BY-NC-ND 4.0)", "rows": rows,
            "differences_found": sum(1 for r in rows if "->" in r["difference"])}


# ------------------------------------------------------------------------------------------------------------------
# (4d) interface demands between the A9 lanes, both directions
# ------------------------------------------------------------------------------------------------------------------
SAT = ("CONSUMED", "VERIFIED", "ANSWERED", "SUPPLIED", "RESOLVED", "SATISFIED", "DELIVERED", "SOURCED", "USED",
       "COPIED_VERIFIED")
OFFER = ("OFFERED", "PRELIMINARY", "PROPOSED", "OWNER_GIVEN", "OWNER_ALLOCATION", "ADOPTED", "DERIVED_BOUND")
PART = ("PARTIAL", "ANSWERED_IN_PART")
# An OPEN / PARTIAL demand must state WHY in its own status (it names what the merged target does not supply), or
# carry an explicit assessment here (checked against the target). A bare 'PENDING' / 'OPEN' fails the build.
VAGUE = re.compile(r"^(PENDING|OPEN|PARTIAL|FLAG|TBD)?\s*(\((revision needed|owner action|LOCK-1|after quotations|"
                   r"hardware not built)\))?$")
ASSESS = {
    ("A9-05ev", "EV-IF-04"): ("OPEN", "owner action: lawful acquisition of LA-01..LA-09 (row 7); A9.1 OQ-EV-02 fixes "
                                      "the order P1 / P2 / P3 and OQ-EV-03 the extraction rule; no lane can do it"),
    ("A9-06", "MA9-ID-22"): ("OPEN", "as-built masses need the S1a hardware (TBD - requires S1a)"),
    ("A9-07", "IDA7-10"): ("OPEN", "ICD ICP-02 / ICP-04 / ICP-07 geometry is TBD, frozen at LOCK-1 (GD-01 before "
                                   "HI-S1); no lane supplies it before the module design"),
    ("A9-09", "IF-RFQ-02"): ("OPEN", "quoted masses exist only after quotations (row 8: quotations only, no purchase)"),
    ("A9-09", "IF-RFQ-08"): ("OPEN", "measured channel data exist only after S1a"),
    ("A9-09", "IF-RFQ-09"): ("OPEN", "ICD geometry / RF ratings / interlock / collector / pressure port are TBD "
                                     "(LOCK-1, GD-01)"),
    ("A9-09", "IF-RFQ-10"): ("OPEN", "certificates and S-parameters exist only after quotations / delivery"),
    ("A9-09", "IF-RFQ-11"): ("OPEN", "the HI-AR flow plan and the Xe reference point size are LOCK-1 items of A9-01 "
                                     "(A9.1 HIQ-03 / HIQ-08 fix placement, not size)"),
    ("A9-INT", "IF-INT-04"): ("PARTIAL", "A9-10 dq_consumer_table gives the chain -> DQ-HI consumer map for the 7 "
                                         "UNMAPPED ids (PROPOSED; ids kept; owner call OQ-INT-01)"),
    ("A9-INT", "IF-INT-05"): ("SATISFIED", "A9-10 pending_reevaluation (this record): filled / re-stated by the "
                                           "A910-R* overlay records or given a checked reason"),
    ("A9-INT", "IF-INT-06"): ("OPEN", "owner call OQ-A910-02 (per-input producing stage / decision quantity at "
                                      "LOCK-1); no assignment is invented"),
    ("A9-INT", "IF-INT-07"): ("SATISFIED", "A9-06 / A9-07 / A9-08 are merged; their references were re-evaluated "
                                           "(pending_reevaluation)"),
}
LANE_TOKENS = [("A9-01", r"A9-01|prereg_framework"), ("A9-02", r"A9-02|power_boundary_a9|bus_boundary_a9"),
               ("A9-03", r"A9-03|icp_neutralizer_icd|interfaces/icp_neutralizer"),
               ("A9-04", r"A9-04|uncertainty_budget"), ("A9-05", r"A9-05|validation_inputs|evidence/icp_neutralizer"),
               ("A9-06", r"A9-06|mass_a9"), ("A9-07", r"A9-07|h2_a9_revisions"),
               ("A9-08", r"A9-08|" + "xe" + r"_ledger_a9"), ("A9-09", r"A9-09|rfq_a9|RFQ-\d\d"),
               ("A9-10", r"A9-10|a9_10_reconciliation|subsystem_maturity_v3"), ("H2/H-1", r"H2-\d|H-1|docs/hardware/h2/")]


def _lanes_in(txt: str) -> list:
    return [k for k, pat in LANE_TOKENS if re.search(pat, txt or "")]


def interface_matrix(errors: list) -> dict:
    rows = []
    srcs = [(d["key"], d["json"]) for d in DELIVERABLES] + [("A9-INT", INTEGRATION["json"])]
    for key, rel in srcs:
        doc = load(rel)
        for x in doc.get("interface_demands", []):
            frm = " ".join(str(x.get(k) or "") for k in ("from", "direction"))
            to = " ".join(str(x.get(k) or "") for k in ("to", "counterpart"))
            qty = x.get("quantity") or x.get("demand") or x.get("what") or ""
            st = str(x.get("status", ""))
            up = st.upper()
            rid = x.get("id") or f"#{doc['interface_demands'].index(x)}"
            if up.startswith("NOT APPLICABLE"):
                cls = "NOT_APPLICABLE"
            elif up.startswith(PART):
                cls = "PARTIAL"
            elif up.startswith(SAT):
                cls = "SATISFIED"
            elif up.startswith(OFFER) and "PENDING" not in up:
                cls = "OFFERED"
            else:
                cls = "OPEN"
            reason, assessed = None, None
            if (key, rid) in ASSESS:
                cls, reason = ASSESS[(key, rid)]
                assessed = "A9-10 assessment (checked against the merged target)"
            elif cls in ("OPEN", "PARTIAL"):
                # the reason is the demand's own status (or, when the status is a bare word, its value text)
                val = str(x.get("value") or "") if not isinstance(x.get("value"), (dict, list)) else ""
                txt = st if not VAGUE.match(st.strip()) else (val if val and not VAGUE.match(val.strip()) else "")
                if not txt or "PENDING" in txt.split(" - ")[0][:8]:
                    errors.append(f"interface demand {key} {rid}: {cls} without a precise reason: {st!r:.120}")
                reason = txt
            rows.append({"lane": key, "id": rid, "from": frm.strip(), "to": to.strip(),
                         "lanes_named": sorted(set(_lanes_in(frm + " " + to)) - {key}), "quantity": str(qty)[:220],
                         "status": st[:400], "class": cls, "open_reason": reason,
                         **({"assessed_by": assessed} if assessed else {})})
    pairs = {}
    for r in rows:
        for other in r["lanes_named"]:
            k = f"{r['lane']} <-> {other}"
            pairs.setdefault(k, {"SATISFIED": 0, "OFFERED": 0, "PARTIAL": 0, "OPEN": 0, "NOT_APPLICABLE": 0})
            pairs[k][r["class"]] += 1
    return {"rule": "every interface demand of every A9 lane (and of the step-1 integration record) is classified "
                    "SATISFIED / OFFERED (content supplied, possibly preliminary) / PARTIAL / OPEN (with the precise "
                    "reason) / NOT_APPLICABLE; both directions are covered because each lane lists its demands to "
                    "and from the others",
            "open_rule": "an OPEN / PARTIAL row states its precise reason (its own status names what the merged target "
                         "does or does not supply, or an A9-10 assessment in ASSESS); a bare PENDING / OPEN fails the "
                         "build",
            "counts": {c: sum(1 for r in rows if r["class"] == c)
                       for c in ("SATISFIED", "OFFERED", "PARTIAL", "OPEN", "NOT_APPLICABLE")},
            "pairs": dict(sorted(pairs.items())), "rows": rows}


# ------------------------------------------------------------------------------------------------------------------
# (5) immutability
# ------------------------------------------------------------------------------------------------------------------
def immutability(errors: list) -> list:
    out = []
    for root, what in IMMUTABLE_ROOTS:
        files = git_ls(root)
        if not files:
            errors.append(f"immutable root {root} has no file at {BASE}")
        for rel in files:
            b = sha256_bytes(git_show(rel))
            p = os.path.join(ROOT, rel)
            n = sha256_file(rel) if os.path.isfile(p) else None
            if b != n:
                errors.append(f"immutable file changed: {rel}")
            out.append({"path": rel, "what": what, "sha256": n, "byte_identical_to_base": b == n})
    return out


# ------------------------------------------------------------------------------------------------------------------
# cross-lane items and new questions
# ------------------------------------------------------------------------------------------------------------------
def cross_lane(errors: list) -> list:
    mass, xe, rfq, icd = load(OV.MASS_A9), load(OV.XE_A9_JSON), load(OV.RFQ_A9), load(OV.ICD)
    clo = mass["wet_closure"]
    r2e = [c for c in clo["cells"] if c["reading"] == "R2E" and c["reference"] == "HARD_40_WET"]
    r0 = [c for c in clo["cells"] if c["reading"] == "R0" and c["reference"] == "HARD_40_WET"]
    split = {r["case_kg"]: r["residual_kg"] for r in xe["design_cases"]["reserve_residual_split"]["rows"]}
    if clo["residual"]["by_case_kg"]["inside_case_XA9Q-01"] != {str(k): v for k, v in split.items()}:
        errors.append("A9-06 residual import differs from the A9-08 reserve_residual_split")
    rq = {q["id"]: q for p in rfq["packages"] for q in p["requirements"]}
    v323 = {r["case_kg"]: r for r in xe["design_cases"]["tank_volume"]["rows"] if r["p_bar"] == 150.0}
    r04 = rq["RFQ-07-R04"]["value"]["V_min_323K_l_by_case_and_MEOP_axis"]
    for c, row in v323.items():
        if r04[f"{c:g} kg"]["150bar"] != row["V_min_323K_l"]:
            errors.append("RFQ-07-R04 tank volume differs from A9-08")
    by = {x["id"]: x for x in icd["items"]}
    return [
        {"id": "XL-01", "item": "A9-06 wet closure re-run with the A9-08 residual imported once",
         "result": {"residual_by_case_kg": clo["residual"]["by_case_kg"],
                    "R2E_vs_40kg_wet_MQ09": {f"{c['xe_case_kg']:g} kg": [c["wet_known_kg"], c["state"]] for c in r2e},
                    "R0_vs_40kg_wet_MQ09": {f"{c['xe_case_kg']:g} kg": [c["wet_known_kg"], c["state"]] for c in r0}},
         "driver": "A9-08 XA9-IF-01 (single booking; XA9-24 f_residual 0.02)", "change": "A910-A906-01",
         "status": "APPLIED; no cell reaches CLOSES (every dry line is still an allocation or evidence floor)"},
        {"id": "XL-02", "item": "A9-06 LV-COIL copper-mass sensitivity on the corrected A9-07 basis (IDA7-01)",
         "result": {"bases": sorted({r["basis"] for r in mass["lv_coil_sensitivity"]["rows"]}),
                    "copper_delta_kg": sorted({r["copper_delta_kg"] for r in mass["lv_coil_sensitivity"]["rows"]})},
         "driver": "A9-07 IDA7-01", "change": "A910-A906-01", "status": "APPLIED (sensitivity only, not booked)"},
        {"id": "XL-03", "item": "A9-09 RFQ ratings from A9-07 (coupler-plane |Gamma|, H3-A907-03/04/15, IDA7-21/22) "
         "and A9-08 (tank ranges at 323 K)", "result": {"RFQ-07-R04_150bar_V_min_l": {k: v["150bar"]
                                                                                      for k, v in r04.items()}},
         "driver": "A9-07 IDA7-21/22, H3-A907-15; A9-08 design_cases", "change": "A910-A909-01..08",
         "status": "APPLIED (quotation only; no purchase order)"},
        {"id": "XL-04", "item": "A9-07 ICP heat allowance (IDA7-07) and exit-face view condition propagated to ICD "
         "ICP-43 / ICP-05", "result": {"ICP-43": by["ICP-43"]["h1_heat_allowance_a9_07"][:160],
                                       "ICP-05": by["ICP-05"]["view_condition_a9_07"][:160]},
         "driver": "A9-07 IDA7-07, K9", "change": "A910-A903-18..21", "status": "APPLIED"},
        {"id": "XL-05", "item": "H2-4 28 V (H3-PPU-05) vs row-111 regulated 100 V internal bus",
         "result": "resolved by owner row 111 for A9 (OQ-RFQ-05 ANSWERED_BY_OWNER_ROW_111)",
         "driver": "row 111", "change": "A910-A909-14", "status": "RECORDED"},
        {"id": "XL-06", "item": "ICD Xe-ledger reference retargeted to the A9 ledger", "result": XE_DIR,
         "driver": "A9.1 HIQ-06 / A9-08", "change": "A910-A903-10", "status": "APPLIED"},
        {"id": "XL-07", "item": "design-case content: A9-08 XA9Q-01 (LOADED Xe incl. reserve + residual) vs A9-06 "
         "MQ-09 (residual on top)", "result": "both readings carried in A9-06 (cells / cells_case_is_loaded); new "
         "owner question OQ-A910-01", "driver": "A9-08 XA9Q-01, A9-06 MQ-09", "change": "A910-A906-01",
         "status": "OPEN (owner call)"},
        {"id": "XL-08", "item": "combined Xe analog range 4.54-12.77 kg (A9 recorder flag) vs H2-7 ID-11 5.044-12.77 kg",
         "result": "not decided here: MQ-08 stays OPEN (owner call); A9-06 uses the verified H2-7 floor 5.044 kg for "
         "AL-08", "driver": "A9-06 MQ-08", "change": None, "status": "OPEN (owner call)"},
        {"id": "XL-09", "item": "RFQ-07-R03 propellant volumes (R6 densities, propellant only) vs A9-08 V_min (loaded "
         "case, EOS uncertainty)", "result": "A9-08 governs the tank ranges (RFQ-07-R04 now carries them; R03 note "
         "re-evaluated)", "driver": "A9-08 design_cases", "change": "A910-A909-22", "status": "APPLIED"},
    ]


# ------------------------------------------------------------------------------------------------------------------
# A9.2 incorporation (owner decisions 2026-09-30, A9-07 follow-up)
# ------------------------------------------------------------------------------------------------------------------
STATUS_KEY = re.compile(r"(^|_)(status|verdict|state|outcome|necessary_check|brief_verdict_at_baseline)$")
A92_PASS = re.compile(r"^(PASS|CLOSES\w*|CLOSED|RESOLVED|CONDITIONALLY_RESOLVED)\b")
# topic of each A9.2 status item: a status-like field claiming a pass inside a record that mentions the topic is a
# violation (thermal limited to the hall_icp_neutralizer thermal recomputation, where the coupled closure lives)
A92_TOPICS = {
    "ICP electron-current capacity": re.compile(r"ICP-45|electron-current capa|electron-extraction .*capab"),
    "ICP RF power closure": re.compile(r"P_ICP,available|ICP RF power|RF power closure"),
    "RF matching architecture": re.compile(r"matching network|local match"),
    "RF component ratings": re.compile(r"TBD_AFTER_IMPEDANCE_MAP|component rating"),
    "316L flight anode": re.compile(r"316L[^\"]{0,80}anode|anode[^\"]{0,80}316L"),
    "final anode material": re.compile(r"anode material"),
    "anode thermal closure": re.compile(r"\bAN\b|anode (worst|thermal|temperature)"),
}
A92_SCAN_FILES = [d["json"] for d in DELIVERABLES] + [M16_V3]


def _dicts(o, p=""):
    if isinstance(o, dict):
        yield p, o
        for k, v in o.items():
            yield from _dicts(v, p + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _dicts(v, p + f"[{i}]")


def a92_status_scan(errors: list) -> dict:
    """No status-like field in the A9 deliverables claims PASS / CLOSES / RESOLVED for an A9.2 status item."""
    hits, checked = [], 0
    for rel in A92_SCAN_FILES:
        doc = load(rel)
        for path, d in _dicts(doc):
            if path.startswith("/a9_10_reconciliation") or "before_a9_2" in path:
                continue
            for k, v in d.items():
                if not STATUS_KEY.search(k) or "sensitivity" in k or "before_a9_2" in k:
                    continue
                vals = v if isinstance(v, list) else [v]
                for x in vals:
                    if not isinstance(x, str):
                        continue
                    checked += 1
                    if not A92_PASS.match(x):
                        continue
                    thermal = "/recomputations/h25_thermal_rerun" in path and "hall_c1_reference" not in path
                    blob = json.dumps(d, ensure_ascii=False)
                    items = (["coupled H-1/ICP thermal closure"] if thermal else []) + \
                        [t for t, rx in A92_TOPICS.items() if rx.search(blob)]
                    if items:
                        hits.append({"file": rel, "pointer": path + "/" + k, "value": x, "items": items})
    for h in hits[:20]:
        errors.append(f"A9.2 status violated: {h['file']}{h['pointer']} = {h['value']!r} ({h['items']})")
    return {"rule": "every status-like field (key ending in status / verdict / state / outcome / necessary_check / "
                    "brief_verdict_at_baseline; *_sensitivity and *_before_a9_2 history fields excluded) of every A9 "
                    "deliverable JSON and M16 v3 is scanned; a PASS / CLOSES* / RESOLVED / CONDITIONALLY_RESOLVED value "
                    "inside the hall_icp_neutralizer thermal recomputation, or inside a record mentioning one of the A9.2 "
                    "status items, is a violation (A9.2 item 9: never convert an open item into PASS)",
            "files": A92_SCAN_FILES, "fields_checked": checked, "violations": hits}


# A9-10 review repair 3: the key-based scan above cannot see pass-like values under non-status keys (REV-42 closure_CO,
# REV-44 PO / BP), status fields outside the recomputation (REV-45) or free text (key findings, register requirements,
# open items, the Curie-check clause, the Markdown), nor supplier-facing RF text rating anything at 500 W. Three more
# scans close that gap; each is proven sensitive on the A9-10 base version in tests/test_a9_10_reconciliation.py.
PASS_TOKEN = re.compile(r"\b(PASS|CLOSES\w*|CONDITIONALLY_RESOLVED)\b")
SENS_LABEL = re.compile(r"uncoupled[ _-]sensitivity|UNRESOLVED|sensitivity only|never a thermal PASS", re.I)
W500 = re.compile(r"(?<![\d.])(0\s*[-\u2013]\s*)?500 W\b")
W500_LABEL = re.compile(r"delivered/operating|not a (sufficient )?component rating|not at (a )?500 W")
W500_SKIP_KEYS = {"quote", "answer_verbatim", "owner_text", "owner_answer_verbatim", "verbatim"}
H2_TEXT_ROOTS = ["/key_findings", "/revision_register", "/interface_demands",
                 "/recomputations/h25_thermal_rerun/overall", "/recomputations/h25_thermal_rerun/bn_wall_11_2K_case",
                 "/recomputations/h25_thermal_rerun/closure_summary_hall_icp_neutralizer",
                 "/recomputations/h25_thermal_rerun/icp_heat_into_h1/note",
                 "/recomputations/h25_thermal_rerun/hall_c1_reference_note"]
H2_VALUE_ROOTS = ["/revision_register", "/recomputations/h25_thermal_rerun/results/hall_icp_neutralizer",
                  "/recomputations/h25_thermal_rerun/closure_summary_hall_icp_neutralizer",
                  "/recomputations/h25_thermal_rerun/bn_wall_11_2K_case",
                  "/recomputations/h25_thermal_rerun/mount_heat_vs_row85", "/recomputations/h25_thermal_rerun/overall"]
RFQ_PACKAGE_DIR = "docs/procurement/rfq_a9/packages/"
W500_FILES = [OV.RFQ_A9, OV.ICD, OV.UB]


def _leaf_items(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _leaf_items(v, p + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _leaf_items(v, p + f"[{i}]")
    else:
        yield p, o


def _skip(path: str) -> bool:
    return "sensitivity" in path or "before_a9_2" in path or path.startswith("/a9_10_reconciliation")


def _h2_icp_register(doc: dict, path: str) -> bool:
    """True unless the path is inside a revision-register row that does not apply to hall_icp_neutralizer, or inside
    its 'old' (historical v1) / 'driver' / 'source' subtrees."""
    m = re.match(r"/revision_register\[(\d+)\](/[^/\[]+)?", path)
    if not m:
        return True
    row = doc["revision_register"][int(m.group(1))]
    return "hall_icp_neutralizer" in row.get("applies_to", []) and (m.group(2) or "") not in ("/old", "/driver",
                                                                                              "/source")


def _bad_sentences(text: str) -> list:
    return [s for s in re.split(r"(?<=\.)\s+", text) if PASS_TOKEN.search(s) and not SENS_LABEL.search(s)]


def a92_text_scan(errors: list, h2: dict = None, h2_md: str = None, w500_docs: dict = None,
                  w500_mds: dict = None) -> dict:
    """(i) pass-like VALUES under any key in the hall_icp_neutralizer thermal records and register rows; (ii) pass-like
    WORDING in A9-07 key findings, register text, open items, Curie / closure summaries and the thermal Markdown without
    an uncoupled-sensitivity / UNRESOLVED label in the same sentence; (iii) supplier-facing / rating text stating
    500 W without the A9.2 delivered/operating label. Inputs default to the committed files (tests pass base copies)."""
    h2 = load(OV.H2A9) if h2 is None else h2
    if h2_md is None:
        with open(os.path.join(ROOT, "docs/hardware/h2_a9_revisions/H2_A9_REVISIONS.md"), encoding="utf-8") as f:
            h2_md = f.read()
    if w500_docs is None:
        w500_docs = {rel: load(rel) for rel in W500_FILES}
    if w500_mds is None:
        w500_mds = {}
        for fn in sorted(os.listdir(os.path.join(ROOT, RFQ_PACKAGE_DIR))):
            if fn.endswith(".md"):
                with open(os.path.join(ROOT, RFQ_PACKAGE_DIR, fn), encoding="utf-8") as f:
                    w500_mds[RFQ_PACKAGE_DIR + fn] = f.read()
    values, wording, w500 = [], [], []
    for path, v in _leaf_items(h2):
        if _skip(path) or not any(path.startswith(r) for r in H2_VALUE_ROOTS) or not _h2_icp_register(h2, path):
            continue
        if isinstance(v, str) and OV.PASS_LIKE.match(v):
            values.append({"pointer": path, "value": v})
        elif v is True and re.search(r"closes", path.rsplit("/", 1)[-1]):
            values.append({"pointer": path, "value": True})
    for path, v in _leaf_items(h2):
        if (not isinstance(v, str) or _skip(path) or not any(path.startswith(r) for r in H2_TEXT_ROOTS)
                or not _h2_icp_register(h2, path) or OV.PASS_LIKE.match(v)):
            continue
        for s in _bad_sentences(v):
            wording.append({"pointer": path, "sentence": s[:200]})
    sec, keep = None, []
    for line in h2_md.splitlines():
        if line.startswith("### ") or line.startswith("## "):
            sec = line
        thermal = sec is not None and (sec.startswith("### Closure summary") or sec.startswith("### The v1 11.2 K"))
        if line.startswith("- K") or line.startswith("| REV-") or (thermal and not line.startswith("|---")):
            keep.append(line)
    for line in keep:
        if line.startswith("| REV-") and "hall_icp_neutralizer" not in line and "REV-4" not in line:
            continue
        for s in _bad_sentences(line):
            wording.append({"pointer": "H2_A9_REVISIONS.md", "sentence": s[:200]})
    for rel, d in w500_docs.items():
        for path, v in _leaf_items(d):
            key = path.rsplit("/", 1)[-1].split("[")[0]
            if (not isinstance(v, str) or "before_a9_2" in path or path.startswith("/a9_10_reconciliation")
                    or key in W500_SKIP_KEYS):
                continue
            if W500.search(v) and not W500_LABEL.search(v):
                w500.append({"file": rel, "pointer": path, "text": v[:200]})
    for rel, txt in w500_mds.items():
        for line in txt.splitlines():
            if W500.search(line) and not W500_LABEL.search(line) and not line.lstrip().startswith(">"):
                w500.append({"file": rel, "pointer": "line", "text": line[:200]})
    for h in (values + wording + w500)[:20]:
        errors.append(f"A9.2 residual wording: {h}")
    return {"rule": "(i) no PASS / CLOSES* / RESOLVED / CONDITIONALLY_RESOLVED value and no True *closes* flag under ANY "
                    "key of the hall_icp_neutralizer thermal records or of a revision-register row applying to "
                    "hall_icp_neutralizer (uncoupled_sensitivity_* / *_before_a9_2 excluded); (ii) every sentence of the "
                    "A9-07 key findings, register text, demands, open items, Curie / closure summaries and thermal "
                    "Markdown that uses PASS / CLOSES* / CONDITIONALLY_RESOLVED carries an uncoupled-sensitivity or "
                    "UNRESOLVED label; (iii) every A9-03 / A9-04 / A9-09 text (JSON and RFQ package Markdown; verbatim "
                    "owner / source quotes excluded) stating 500 W carries the A9.2 delivered/operating label",
            "value_violations": values, "wording_violations": wording, "w500_violations": w500,
            "violations": values + wording + w500}


def a92_section(recs: dict, errors: list) -> dict:
    dec = load(OV.A92_COPY)
    for rel, sha in ((OV.A92_COPY, OV.A92_SHA), (OV.A92_MD_COPY, OV.A92_MD_SHA)):
        if sha256_file(rel) != sha:
            errors.append(f"A9.2 pinned copy changed: {rel}")
    for rel, sha in ((OV.A92_REL, OV.A92_SHA), (OV.A92_MD_REL, OV.A92_MD_SHA)):
        if os.path.isfile(os.path.join(ROOT, rel)) and sha256_file(rel) != sha:
            errors.append(f"A9.2 decision file differs from its pin: {rel}")
    st = dec["decisions"]["a9_10_statuses"]
    want = {"Hall->ICP architecture": "INVESTIGATION_HYPOTHESIS", "ICP electron-current capacity": "PENDING_ICP45",
            "ICP RF power closure": "PENDING_HARDWARE", "RF matching architecture": "LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT",
            "RF component ratings": "TBD_AFTER_IMPEDANCE_MAP", "316L flight anode": "REJECTED_AS_CURRENT_BASELINE",
            "final anode material": "OPEN", "anode thermal closure": "UNRESOLVED",
            "coupled H-1/ICP thermal closure": "UNRESOLVED", "C1 conventional reference": "CONTROL_FALLBACK"}
    if st != want:
        errors.append("A9.2 status table differs from the verbatim item 9")
    cover = []
    for key in dec["decisions"]:
        cids = sorted({r["cid"] for rs in recs.values() for r in rs
                       if re.search(r"A9\.2\b[^|]*\b" + re.escape(key) + r"\b", r["driver"])})
        cover.append({"decision": key, "applied_by": cids,
                      "status": "APPLIED" if cids else "RECORDED (process / scope item; no deliverable field)"})
    must = ["OQ-A907-11", "rf_measurement_reference", "rf_500W", "rf_protection", "icp_matching_strategy", "anode_316L",
            "anode_approach", "icp_coupled_thermal", "radiative_view_requirement", "13W_pole_allowance",
            "coil_mass_correction", "a9_10_statuses"]
    for c in cover:
        if c["decision"] in must and not c["applied_by"]:
            errors.append(f"A9.2 {c['decision']} not applied to any deliverable")
    h2 = load(OV.H2A9)
    th = h2["recomputations"]["h25_thermal_rerun"]
    return {
        "decision": OV.a92_pin(),
        "statuses": [{"item": k, "status": v} for k, v in st.items()],
        "statuses_rule": "verbatim A9.2 item 9; none of them is converted into PASS to close A9-10 (a9_2_status_scan)",
        "supersession": {"id": "SUP-A92-01", "superseded": "A9.1 A9-03-matching: matching network off the moving "
                         "platform, long flexible coax, coupler reference plane after the match",
                         "by": "A9.2 OQ-A907-11: " + OV.LOCAL_CHAIN, "scope": "the A9 baseline (history kept: the A9.1 "
                         "value is preserved as *_before_a9_2 fields and in REV-34 / ICPQ-05 records; nothing deleted)"},
        "rf_chain": {"chain": OV.LOCAL_CHAIN, "measurement": OV.MEAS_REF, "ratings": OV.RATINGS_TBD,
                     "protection": OV.PROTECTION, "trip_thresholds": OV.TRIP_TBD,
                     "matching_strategy": "adjustable local match for the development article; flight implementation "
                                          "(fixed / switched / electronically tuned / other) only after Z_antenna = R + "
                                          "jX is mapped vs mdot, P_RF, p, gas composition and the Hall operating point"},
        "anode": {"ANODE_BASELINE": "OPEN", "text": OV.ANODE_TEXT, "investigate": OV.ANODE_INVESTIGATION,
                  "design_blockers": [{"id": "A9H-ANODE-01", "what": "anode material", "m16_row": 20},
                                      {"id": "A9H-ANODE-02", "what": "anode heat-removal path", "m16_row": 21}],
                  "no_rfq_implied": True},
        "coupled_thermal": {"ICP_COUPLED_THERMAL": th["a9_2_icp_coupled_thermal"]["ICP_COUPLED_THERMAL"],
                            "required_terms": OV.COUPLED_TERMS, "statement": OV.COUPLED_TEXT,
                            "pole_allowance_warning": th["a9_2_icp_coupled_thermal"]["pole_allowance_warning"],
                            "overall_status_now": th["overall"]["status"],
                            "radiative_view_objective": {"icd_item": "ICP-47", "objectives": OV.VIEW_OBJECTIVE},
                            "prohibited_assumption": "ICP thermal interaction is small enough to ignore"},
        "coil_mass_correction": OV.COIL_TEXT,
        "decision_coverage": cover,
        "recommended_next_lanes_not_launched": OV.POST_A9,
        "pr_33": "keep DRAFT (A9.2 item 11): after A9-10 merges into the execution branch run the full suite, golden "
                 "checks, integrity checks, historical immutable hashes, a complete A9 diff review and confirm this "
                 "record carries the RF / anode / thermal blockers; only then convert PR #33 to ready (orchestrator / "
                 "owner action, not performed by this lane)",
        "status_scan": a92_status_scan(errors),
        "text_scan": a92_text_scan(errors),
    }


NEW_QUESTIONS = [
    {"id": "OQ-A910-01", "question": "Which content do the row-48 Xe design cases have for BOTH the A9 Xe ledger and "
     "the A9 mass BOM: LOADED Xe incl. reserve and residual (A9-08 XA9Q-01) or usable Xe incl. reserve with the "
     "residual on top (A9-06 MQ-09)? The two lanes propose different readings.",
     "proposed_answer": "owner call; A9-10 carries both readings (A9-06 wet_closure cells vs cells_case_is_loaded; the "
     "difference is the residual, <= 0.2 kg at 10 kg); one reading should govern both lanes",
     "needed_by": "LOCK-1 (tank RFQ ranges RFQ-07-R04, wet closure)", "raised_by": "A9-10"},
    {"id": "OQ-A910-02", "question": "Assign the producing stage and the decision quantity of each A9-05 validation "
     "input (98 producing_stage / decision_quantity_ids fields, now reading 'TBD - ASSIGNMENT_NOT_DEFINED_BY_TARGET "
     "... owner call OQ-A910-02', overlay A910-R05-01/02)?", "proposed_answer": "assign at LOCK-1 from the A9-01 stage map and the A9-10 chain -> DQ-HI "
     "consumer table (dq_consumer_table); no assignment is invented here; owner call",
     "needed_by": "LOCK-1", "raised_by": "A9-10"},
    {"id": "OQ-A910-03", "question": "May a ledger declared 'peak_sampled' (the unaveraged sampled peak) PASS the "
     "1.5 kW gate when the peak is below 1500 W and the record meets the A9.1 OQ-A902-01 measurement requirements "
     "(the maximum 1 ms mean cannot exceed the maximum sample)? A9.1 OQ-A902-01 calls the unaveraged peak 'protection "
     "analysis only; not the 1.5 kW gate', so A9-02 does NOT implement this reading: today only a declared "
     "p_bus_1ms_max ledger with a conformant gate_measurement record can PASS, and a peak_sampled ledger is "
     "NOT_EVALUABLE in both directions.",
     "proposed_answer": "PROPOSED yes, limited to records meeting >= 100 kSa/s, >= 20 kHz, documented anti-alias "
                        "filtering and synchronized channels (it is conservative and never substitutes a step "
                        "average); owner call - not implemented until answered", "needed_by": "LOCK-1",
     "raised_by": "A9-10"},
    {"id": "OQ-A910-04", "question": "Accept the location of the M16 v3 JSON at " + M16_V3 + " instead of the "
     "brief-named docs/budgets/subsystem_maturity/subsystem_maturity_v3.json? The immutable H2-7 v1 mechanical BOM "
     "builder scans docs/budgets/subsystem_maturity/*.json non-recursively and pins every file it finds, so any new "
     "JSON there makes the H2-7 v1 --check stale (verified). The builder and the Markdown keep the brief-named paths "
     "(docs/budgets/subsystem_maturity/build_subsystem_maturity_v3.py, SUBSYSTEM_MATURITY_v3.md).",
     "proposed_answer": "PROPOSED accept (the alternative is to change the immutable H2-7 v1 builder, which is not "
                        "allowed); orchestrator / owner call", "needed_by": "merge of this lane",
     "raised_by": "A9-10"},
    {"id": "OQ-A910-05", "question": "With the A9.2 local matching network on / adjacent to the ICP module (moving "
     "platform), the matched sham configuration (row 133) must present the same service-line parasitics. Should the "
     "hall_c1_reference sham carry a mass / stiffness / thermal equivalent of the on-module match (not only a sham "
     "coax), and which of the A9-06 allocation lines (AL-05 ICP head or AL-06 RF) books the local match hardware?",
     "proposed_answer": "PROPOSED yes (sham equivalent of the on-module match, value TBD - requires the match "
                        "selection); allocation line: owner call together with MQ-07 (A9-06 keeps it on AL-06, no "
                        "number changed)", "needed_by": "LOCK-1 (ICD ICP-08 / ICP-18, A9-06 AL-05/06)",
     "raised_by": "A9-10 (A9.2 incorporation)"},
]
SCOPE_DEVIATIONS = [
    {"id": "SD-A910-01", "item": "M16 v3 JSON location", "brief_path": "docs/budgets/subsystem_maturity/"
     "subsystem_maturity_v3.json", "actual_path": M16_V3, "within_allowed_paths": True,
     "reason": "the immutable H2-7 v1 builder (docs/hardware/h2/h2_7_mechanical_bom/build_h2_7_mechanical_bom.py, "
               "lane_consumption) globs docs/budgets/subsystem_maturity/*.json and pins each file's sha256; a new JSON "
               "there makes H2-7 v1 --check STALE (verified by copying the file there and running the check)",
     "companion_files_at_brief_paths": ["docs/budgets/subsystem_maturity/build_subsystem_maturity_v3.py",
                                        "docs/budgets/subsystem_maturity/SUBSYSTEM_MATURITY_v3.md"],
     "status": "DECLARED; orchestrator acceptance requested (OQ-A910-04)"},
]


# ------------------------------------------------------------------------------------------------------------------
# build
# ------------------------------------------------------------------------------------------------------------------
def build():
    errors = []
    pins = []
    for rel, sha, what in AUTHORITY_PINS:
        got = sha256_file(rel)
        if got != sha:
            errors.append(f"authority pin mismatch {rel}")
        pins.append({"path": rel, "sha256": got, "what": what})
    recs = OV.records()
    by_deliv = []
    for d in DELIVERABLES:
        by_deliv.append(verify_deliverable(d, recs[d["key"]], errors))
    # A9.1 decision coverage
    a91 = load(OV.A91_REL)["decisions"]
    applied = {}
    for rs in recs.values():
        for r in rs:
            for did in re.findall(r"(HIQ-0\d|UBQ-0\d|OQ-A902-0\d|OQ-EV-0\d|ICP-4[56]|A9-03-[a-zA-Z]+|SEQ-[a-z]+)",
                                  r["driver"] + " " + str(r.get("summary"))):
                applied.setdefault(did, []).append(r["cid"])
    coverage = []
    for did in a91:
        base_id = did.replace("_accounting", "")
        cids = sorted(set(applied.get(base_id, [])))
        coverage.append({"decision": did, "applied_by": cids,
                         "status": "APPLIED" if cids else "RECORDED (no deliverable field to change)"})
    missing = [c["decision"] for c in coverage if not c["applied_by"] and not c["decision"].endswith("_accounting")]
    if missing:
        errors.append(f"A9.1 decisions not applied anywhere: {missing}")
    pend = pending_reevaluation(errors)
    cons = dq_consumer_table(errors)
    annex = annex_reconciliation(errors)
    ifm = interface_matrix(errors)
    imm = immutability(errors)
    xl = cross_lane(errors)
    a92 = a92_section(recs, errors)
    pins_now = []
    for d in DELIVERABLES + [dict(INTEGRATION, key="A9-INT")]:
        for rel in [d["json"], d["md"], d["builder"]] + d.get("extra", []):
            pins_now.append({"deliverable": d["key"], "path": rel, "sha256": sha256_file(rel),
                             "changed_since_base": sha256_file(rel) != sha256_bytes(git_show(rel))})
    pins_now.append({"deliverable": "A9-10", "path": OV.OVERLAY_REL, "sha256": sha256_file(OV.OVERLAY_REL),
                     "changed_since_base": True})
    n_changes = sum(len(x["changes"]) for x in by_deliv)
    items = [
        {"id": "REC-01", "name": "declared A9-10 changes to the A9 deliverables", "value": n_changes, "units": "count",
         "basis": "a9_10_overlay.py records", "source": "computed by this builder", "evidence_class": "inferred",
         "status": "APPLIED", "freeze_point": "NOW"},
        {"id": "REC-02", "name": "changed leaves not explained by a declared change",
         "value": sum(x["unexplained"] + x["numeric_unexplained"] for x in by_deliv), "units": "count",
         "basis": "leaf diff vs the A9-10 base " + BASE, "source": "computed by this builder",
         "evidence_class": "inferred", "status": "VERIFIED (must be 0)", "freeze_point": "NOW"},
        {"id": "REC-03", "name": "A9.1 decisions applied to at least one deliverable",
         "value": sum(1 for c in coverage if c["applied_by"]), "units": "count", "basis": "A9.1 decisions",
         "source": OV.A91_REL, "evidence_class": "inferred", "status": "APPLIED", "freeze_point": "NOW"},
        {"id": "REC-04", "name": "PENDING occurrences at the A9-10 base / now",
         "value": [sum(x["pending_at_base"] for x in pend["per_deliverable"]),
                   sum(x["pending_now"] for x in pend["per_deliverable"])], "units": "count",
         "basis": "OQ-INT-03", "source": "computed by this builder", "evidence_class": "inferred",
         "status": "RE-EVALUATED (every remaining one carries a reason code)", "freeze_point": "NOW"},
        {"id": "REC-05", "name": "gate quantity P_bus,1ms,max < 1500 W (start-up and steady state)",
         "value": {"window_s": 0.001, "limit_W": 1500.0, "min_bandwidth_Hz": 20000.0, "min_sample_rate_Sa_s": 100000.0},
         "units": "s, W, Hz, Sa/s", "basis": "owner decision", "source": OV.A91_REL + " OQ-A902-01",
         "evidence_class": "owner-allocation", "status": "APPLIED (A9-02)", "freeze_point": "NOW"},
        {"id": "REC-06", "name": "statistical rule constants", "value": {"alpha_family_wise": 0.05,
                                                                        "alpha_one_sided_gate": 0.05, "k_x": 2.0,
                                                                        "thrust_u_k": 1},
         "units": "-", "basis": "owner decision", "source": OV.A91_REL + " UBQ-01, UBQ-04, UBQ-07",
         "evidence_class": "owner-allocation", "status": "APPLIED (A9-01, A9-04)", "freeze_point": "LOCK-1"},
        {"id": "REC-07", "name": "keeper-pulse isolation basis / development hipot / pulse test",
         "value": [900.0, 1000.0, 600.0], "units": "V", "basis": "owner decision", "source": OV.A91_REL + " ICP-46",
         "evidence_class": "owner-allocation", "status": "APPLIED (A9-03 ICP-46)", "freeze_point": "NOW"},
        {"id": "REC-08", "name": "immutable / historical files byte-identical to the A9-10 base",
         "value": sum(1 for x in imm if x["byte_identical_to_base"]), "units": "count", "basis": "A9 supersession rule",
         "source": "computed by this builder", "evidence_class": "inferred", "status": "VERIFIED",
         "freeze_point": "NOW"},
        {"id": "REC-10", "name": "A9.2 statuses carried verbatim (item 9)", "value": len(a92["statuses"]),
         "units": "count", "basis": "owner decision A9.2", "source": OV.A92_REL + " a9_10_statuses",
         "evidence_class": "owner-allocation", "status": "APPLIED (none converted to PASS)", "freeze_point": "NOW"},
        {"id": "REC-11", "name": "status-like fields claiming PASS / CLOSES / RESOLVED for an A9.2 item",
         "value": len(a92["status_scan"]["violations"]), "units": "count", "basis": "A9.2 item 9",
         "source": "computed by this builder (a9_2.status_scan)", "evidence_class": "inferred",
         "status": "VERIFIED (must be 0)", "freeze_point": "NOW"},
        {"id": "REC-12", "name": "residual A9.2 wording: pass-like values under any key, PASS / CLOSES sentences "
         "without an uncoupled-sensitivity label, 500 W texts without the delivered/operating label",
         "value": len(a92["text_scan"]["violations"]), "units": "count", "basis": "A9.2 icp_coupled_thermal, rf_500W",
         "source": "computed by this builder (a9_2.text_scan)", "evidence_class": "inferred",
         "status": "VERIFIED (must be 0)", "freeze_point": "NOW"},
        {"id": "REC-09", "name": "interface demands classified (A9 lanes + step-1 record)",
         "value": len(ifm["rows"]), "units": "count", "basis": "task scope (2)", "source": "computed by this builder",
         "evidence_class": "inferred", "status": "CLASSIFIED", "freeze_point": "NOW"},
    ]
    doc = {
        "schema": "a9_10_reconciliation_v1", "id": "a9_10_reconciliation_v1", "lane": "fo_a9_10_integration",
        "trigger": "T_A9_10_INTEGRATION", "owner_step": "A9.1 section 9 step 3 (A9-10)",
        "status": "RECONCILIATION_RECORD_NOT_A_SCIENTIFIC_RESULT", "a9_status": A9_STATUS, "base_commit": BASE,
        "generated_by": SCRIPT_REL + " (--check reproduces JSON and MD exactly and re-runs every check)",
        "companion_document": MD_REL, "test": TEST_REL, "overlay": OV.OVERLAY_REL,
        "configurations": list(CONFIGURATIONS), "outcome_vocabulary": list(CONFIGURATIONS) + ["NO_VIABLE_CASE"],
        "status_not_outcome": ["OPEN"],
        "what_this_is_not": [
            "not a performance prediction (no thrust, efficiency, discharge current, electron current or plasma state)",
            "not an architecture selection: no winner; A9 stays " + A9_STATUS + "; Bundle 1 NO_BASELINE_YET; credible "
            "Hall set EMPTY; P5-N2 v1 INCONCLUSIVE",
            "not an answer to any OPEN owner question (answers come only from the owner; A9.1 decisions are applied "
            "as given)",
            "not a change to any immutable / historical file (immutability section)"],
        "authority_pins": pins, "governance_files_not_pinned": GOVERNANCE_NOT_PINNED,
        "items": items,
        "changes_by_deliverable": by_deliv,
        "a9_1_decision_coverage": coverage,
        "cross_lane_reconciliation": xl,
        "a9_2": a92,
        "pending_reevaluation": pend,
        "dq_consumer_table": cons,
        "annex_reconciliation": annex,
        "interface_demand_matrix": ifm,
        "integration_record": {"path": INTEGRATION["json"], "status": "frozen step-1 snapshot (compared at "
                               + BASE + "); OQ-INT-01 OPEN (owner call; consumer table PROPOSED here), OQ-INT-02 "
                               "OPEN, OQ-INT-03 / OQ-INT-04 addressed here (OQ-INT-03: fields filled or re-stated by "
                               "the A910-R* records, remaining ones with a target-checked reason, no catch-all)"},
        "scope_deviations": SCOPE_DEVIATIONS,
        "current_pins": pins_now,
        "immutability": imm,
        "interface_demands": [
            {"id": "IF-A910-01", "direction": "from every A9 lane to A9-10", "counterpart": "A9-01..A9-09",
             "quantity": "open owner questions, m16_impact, interface demands, PENDING references", "units": "-",
             "status": "CONSUMED"},
            {"id": "IF-A910-02", "direction": "from A9-10 to M16", "counterpart": M16_V3,
             "quantity": "row refresh (rows 1-17), row 17 superseded, new rows 18-19; A9.2 anode design-blocker "
                         "rows 20-21 and per-row A9.2 statuses", "units": "-",
             "status": "SUPPLIED"},
            {"id": "IF-A910-03", "direction": "from A9-10 to the owner", "counterpart": OQ_V2,
             "quantity": "owner-question state v2 (147 rows + A9.1 + A9.2 + every new lane question; OQ-A907-11 "
                         "ANSWERED_BY_A9_2)", "units": "-",
             "status": "SUPPLIED"},
            {"id": "IF-A910-04", "direction": "from A9-10 to H3 / H4", "counterpart": "A9-09 RFQ packages; A9-02 H4",
             "quantity": "RFQ rating updates (RFQ-04 coupler/coax/pre-match, RFQ-07 tank ranges); 1 ms P_bus "
                         "metering channel", "units": "-", "status": "SUPPLIED (quotation only)"}],
        "owner_answers_applied": [
            {"row": 111, "how_applied": "H2-4 28 V vs regulated 100 V internal bus recorded as resolved by row 111 for "
                                        "A9 (OQ-RFQ-05)"},
            {"row": 140, "how_applied": "M16 v3: every row carries a functional-role owner until a named engineer is "
                                        "assigned; Praveen remains accountable system owner"},
            {"row": 141, "how_applied": "M16 v3 keeps the accepted scheduler rule, one-blocker rule and non-lane-input "
                                        "guard"},
            {"row": 142, "how_applied": "A9 lanes added to the lane-to-row mapping without rewriting H2 provenance"},
            {"row": 143, "how_applied": "every divergence found here is explicit (cross_lane_reconciliation, "
                                        "new_open_questions), none left silent"},
            {"row": 144, "how_applied": "every M16 v3 blocker states its latest decision point (LOCK-1 / LOCK-2)"},
            {"row": 38, "how_applied": "OPEN is a status, not an outcome"},
            {"row": 37, "how_applied": "no weighted scalar; no winner"}],
        "new_open_questions": NEW_QUESTIONS,
        "open_owner_questions": NEW_QUESTIONS,
        "remaining_open_items": {
            "owner_questions_state": OQ_V2 + " (OPEN rows with a yellow 'Your answer' column in the xlsx; review "
                                     "repair 3: the A9.1 A9-03-matching decision row and ICPQ-05 carry an explicit "
                                     "A9.2 OQ-A907-11 supersession pointer; OPEN ICPQ-10 / ICPQ-11 are marked "
                                     "A9.2-affected (rf_500W, icp_matching_strategy) with needed-by after the impedance "
                                     "map, still OPEN)",
            "m16_v3_location": "SD-A910-01: M16 v3 JSON kept at " + M16_V3 + " (the immutable H2-7 v1 builder globs "
                               "docs/budgets/subsystem_maturity/*.json); acceptance of the location stays OPEN as "
                               "OQ-A910-04 (owner / orchestrator call; file not moved)",
            "integration": ["OQ-INT-01 (consumer table PROPOSED)", "OQ-INT-02"],
            "pending_by_reason": pend["remaining_by_reason"],
            "interface_demands_open": ifm["counts"]["OPEN"] + ifm["counts"]["PARTIAL"],
            "m16": M16_V3 + " (every row BLOCKED or READY per the accepted scheduler rule; named owners missing)",
            "a9_2_blockers": ["RF component ratings TBD_AFTER_IMPEDANCE_MAP (P2)", "ICP electron-current capacity "
                              "PENDING_ICP45 (P1)", "ICP RF power closure PENDING_HARDWARE", "coupled H-1/ICP thermal "
                              "closure UNRESOLVED (P3; A9H-TH-01, ICD ICP-47)", "anode material OPEN (A9H-ANODE-01, P4)",
                              "anode thermal closure UNRESOLVED (A9H-ANODE-02, P4)"]},
        "historical_reuse": {
            "reused": ["docs/experiments/hall_icp/integration/build_a9_core_integration.py: leaf-by-leaf comparison "
                       "and immutability pattern (git show at a pinned commit)",
                       "docs/budgets/subsystem_maturity/build_subsystem_maturity.py (M16 v2): scheduler rule and "
                       "waits_on vocabulary, re-used by the v3 builder"],
            "not_reused": ["A5 Phase-1 prereg framework, pre-ionizer module ICD, LOCK-1 drafts, bus_power_boundary_v1, "
                           "A8 / RF||Hall v2: nothing reused; byte-identity verified (immutability)"]},
        "m16_impact": {"file": M16_V3, "rows_touched": list(range(1, 22)),
                       "note": "v1 and v2 unchanged; v3 adds rows 18 (ICP neutralizer head) and 19 (flight RF chain) "
                               "and marks row 17 superseded for the primary line; A9.2 adds the anode design-blocker "
                               "rows 20 (material) and 21 (heat-removal path), re-points rows 13 / 15 to the coupled "
                               "thermal model / impedance map and carries the A9.2 statuses per row"},
        "h3_h4_inputs": {"h3": ["RFQ-04-R06/R07/R08/R11/R12 re-stated for the A9.2 local match (coupler on the "
                                "generator / 50-ohm side; ratings TBD_AFTER_IMPEDANCE_MAP)",
                                "RFQ-04-R15 optional fixed pre-match SUPERSEDED_BY_A9_2; RFQ-04-R16 RF protection, "
                                "RFQ-04-R17 local-match mass and V/I, RFQ-05-R13 on-module match provision (all TBD)",
                                "no anode RFQ implied (A9.2)",
                                "RFQ-07-R04 tank V_min per case at 323 K (A9-08)"],
                         "h4": ["P_bus,1ms,max channel: >= 20 kHz, >= 100 kSa/s, synchronized, anti-alias "
                                "documented (A9-02 H4-A902-03)",
                                "ICP-45A (Ar) / ICP-45N (N2) electron-current capacity records (A9-03 ICP-45)",
                                "ICP-46 1.0 kV DC hipot + 600 V pulse test (A9-03)",
                                "A9.2 P1 ICP electron-source bench I_e(P_RF, Z, p, mdot, gas) and P2 impedance map "
                                "Z_antenna = R + jX (recommended next lanes, not launched)"]},
        "compliance": [
            "every change has a driver; every changed number is explained by an A9.1 decision or a verified upstream "
            "value (machine-checked)", "immutable inputs pinned by sha256; mutable governance never pinned",
            "no screening candidate or unadmitted Hall closure used; no winner declared; no prediction",
            "no source contacted; no network used"],
        "errors": errors,
    }
    return doc, errors


# ------------------------------------------------------------------------------------------------------------------
# markdown
# ------------------------------------------------------------------------------------------------------------------
def _c(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)
    return str(v).replace("|", "\\|").replace("\n", " ")


def render_md(d) -> str:
    L = []
    a = L.append
    a("# A9-10 reconciliation (fo_a9_10_integration)")
    a("")
    a(f"<!-- GENERATED by {SCRIPT_REL} from a9_10_reconciliation_v1.json; do not edit by hand -->")
    a("")
    a(f"Status **{d['status']}**; A9 stays **{d['a9_status']}**. Base `{d['base_commit']}`. Overlay `{d['overlay']}`. "
      "No winner, no prediction; no OPEN owner question is answered here.")
    a("")
    for w in d["what_this_is_not"]:
        a(f"* {w}")
    a("")
    a("## (a) Items")
    a("")
    a("| id | name | value | units | basis | source | evidence class | status | freeze point |")
    a("|---|---|---|---|---|---|---|---|---|")
    for it in d["items"]:
        a(f"| {it['id']} | {_c(it['name'])} | {_c(it['value'])} | {it['units']} | {_c(it['basis'])} | "
          f"{_c(it['source'])} | {it['evidence_class']} | {_c(it['status'])} | {it['freeze_point']} |")
    a("")
    a("## Changes by deliverable (every change with its driver)")
    a("")
    for x in d["changes_by_deliverable"]:
        a(f"### {x['deliverable']} - `{x['file']}`")
        a("")
        a(f"Changed leaves vs base: {x['changed_leaves']} (explained: {_c(x['explained_by'])}; unexplained "
          f"{x['unexplained']}; numeric changed {x['numeric_leaves_changed']}, unexplained numeric "
          f"{x['numeric_unexplained']}).")
        a("")
        a("| change | driver | op | pointer / file | count | summary |")
        a("|---|---|---|---|---|---|")
        for c in x["changes"]:
            a(f"| {c['cid']} | {_c(c['driver'])} | {c['op']} | `{_c(c['ptr'])}` | {_c(c['count'])} | "
              f"{_c(c['summary'])} |")
        a("")
    a("## A9.1 decision coverage")
    a("")
    a("| decision | applied by | status |")
    a("|---|---|---|")
    for c in d["a9_1_decision_coverage"]:
        a(f"| {c['decision']} | {', '.join(c['applied_by']) or '-'} | {c['status']} |")
    a("")
    a("## Cross-lane reconciliation")
    a("")
    for x in d["cross_lane_reconciliation"]:
        a(f"* **{x['id']}** {x['item']}: {_c(x['result'])} (driver {x['driver']}; change {_c(x['change'])}; "
          f"{x['status']})")
    a("")
    g = d["a9_2"]
    a("## A9.2 incorporation (owner decisions 2026-09-30, A9-07 follow-up)")
    a("")
    a(f"Decision `{g['decision']['path']}` (sha256 `{g['decision']['sha256']}`), verbatim `{g['decision']['verbatim']}` "
      f"(sha256 `{g['decision']['verbatim_sha256']}`); read from the byte-identical pinned copy "
      f"`{g['decision']['pinned_copy']}` (recorded at commit {g['decision']['recorded_at_commit']}).")
    a("")
    a("### A9.2 statuses (verbatim, item 9)")
    a("")
    a("| item | status |")
    a("|---|---|")
    for x in g["statuses"]:
        a(f"| {_c(x['item'])} | **{x['status']}** |")
    a("")
    a(g["statuses_rule"] + ". Status scan: " + f"{g['status_scan']['fields_checked']} status-like fields checked, "
      f"{len(g['status_scan']['violations'])} violations. Text scan (review repair 3): "
      f"{len(g['text_scan']['violations'])} violations ({g['text_scan']['rule']}).")
    a("")
    sp = g["supersession"]
    a(f"* **{sp['id']}** superseded: {sp['superseded']}; by {sp['by']}; scope: {sp['scope']}.")
    a(f"* **RF chain**: {_c(g['rf_chain']['chain'])}. Measurement: {_c(g['rf_chain']['measurement'])}. Ratings: "
      f"{_c(g['rf_chain']['ratings'])}. Protection: {', '.join(g['rf_chain']['protection'])}; "
      f"{_c(g['rf_chain']['trip_thresholds'])}. Matching strategy: {_c(g['rf_chain']['matching_strategy'])}.")
    a(f"* **Anode**: ANODE_BASELINE = {g['anode']['ANODE_BASELINE']}. {_c(g['anode']['text'])}. Investigate: "
      f"{'; '.join(g['anode']['investigate'])}. Design blockers: "
      + "; ".join(f"{b['id']} ({b['what']}, M16 v3 row {b['m16_row']})" for b in g["anode"]["design_blockers"])
      + ". No anode RFQ implied.")
    ct = g["coupled_thermal"]
    a(f"* **Coupled thermal**: ICP_COUPLED_THERMAL = {ct['ICP_COUPLED_THERMAL']} (A9-07 overall now "
      f"{ct['overall_status_now']}). {_c(ct['statement'])}. Pole warning: {_c(ct['pole_allowance_warning']['text'])} "
      f"({ct['pole_allowance_warning']['value_W']} W, {ct['pole_allowance_warning']['source']}). Radiative-view "
      f"objective {ct['radiative_view_objective']['icd_item']}: {'; '.join(ct['radiative_view_objective']['objectives'])}.")
    a(f"* **Coil-mass correction**: {_c(g['coil_mass_correction'])}.")
    a(f"* **PR #33**: {_c(g['pr_33'])}.")
    a("")
    a("### A9.2 decision coverage")
    a("")
    a("| A9.2 item | applied by | status |")
    a("|---|---|---|")
    for c in g["decision_coverage"]:
        a(f"| {c['decision']} | {', '.join(c['applied_by']) or '-'} | {c['status']} |")
    a("")
    a("### Recommended next lanes (A9.2 item 12; not launched)")
    a("")
    for x in g["recommended_next_lanes_not_launched"]:
        a(f"* **{x['id']} {x['name']}**: {x['measure']} (moves: {x['status_it_moves']})")
    a("")
    p = d["pending_reevaluation"]
    a("## PENDING re-evaluation (OQ-INT-03)")
    a("")
    a(p["rule"] + ".")
    a("")
    a("| deliverable | PENDING at base | PENDING now | leaves no longer PENDING |")
    a("|---|---|---|---|")
    for x in p["per_deliverable"]:
        a(f"| {x['deliverable']} | {x['pending_at_base']} | {x['pending_now']} | {x['leaves_no_longer_pending']} |")
    a("")
    a("| reason code | remaining | meaning |")
    a("|---|---|---|")
    for k, n in p["remaining_by_reason"].items():
        a(f"| {k} | {n} | {_c(p['reason_codes'][k])} |")
    a("")
    det = [x for x in p["remaining"] if x.get("detail")]
    if det:
        a("| deliverable | pointer | checked detail |")
        a("|---|---|---|")
        for x in det:
            a(f"| {x['deliverable']} | `{x['pointer']}` | {_c(x['detail'])} |")
        a("")
    cons = d["dq_consumer_table"]
    a("## Chain -> DQ-HI consumer table (OQ-INT-01, PROPOSED; ids kept)")
    a("")
    a("| UB-DQ id | primary INS | declared DQ-HI consumers | DQ-HI sharing the primary instrument | status |")
    a("|---|---|---|---|---|")
    for r in cons["rows"]:
        a(f"| {r['ub_dq_id']} | {_c(r['primary_ins'])} | {', '.join(r['dq_hi_consumers_declared']) or '-'} | "
          f"{', '.join(r['dq_hi_sharing_primary_instrument']) or '-'} | {r['status']} |")
    a("")
    an = d["annex_reconciliation"]
    a("## A9-03 annex vs A9-05 extraction (OQ-INT-04; A9-05 governs)")
    a("")
    a(an["rule"] + ". Source: " + an["source"] + ".")
    a("")
    a("| A9-03 | A9-05 | difference |")
    a("|---|---|---|")
    for r in an["rows"]:
        a(f"| {r['a9_03_id']} | {', '.join(r['a9_05_ids'])} | {_c(r['difference'])} |")
    a("")
    ifm = d["interface_demand_matrix"]
    a("## (b) Interface demands between the A9 lanes (both directions)")
    a("")
    a(ifm["rule"] + f". Counts: {_c(ifm['counts'])}.")
    a("")
    a("| lane pair | satisfied | offered | partial | open | n/a |")
    a("|---|---|---|---|---|---|")
    for k, v in ifm["pairs"].items():
        a(f"| {k} | {v['SATISFIED']} | {v['OFFERED']} | {v['PARTIAL']} | {v['OPEN']} | {v['NOT_APPLICABLE']} |")
    a("")
    a("| lane | id | class | status / open reason |")
    a("|---|---|---|---|")
    for r in ifm["rows"]:
        if r["class"] in ("OPEN", "PARTIAL"):
            a(f"| {r['lane']} | {r['id']} | {r['class']} | {_c(r['open_reason'])[:260]} |")
    a("")
    for x in d["interface_demands"]:
        a(f"* **{x['id']}** {x['direction']} ({x['counterpart']}): {x['quantity']} - {x['status']}")
    a("")
    a("## (c) Owner answers applied")
    a("")
    for x in d["owner_answers_applied"]:
        a(f"* row {x['row']}: {x['how_applied']}")
    a("")
    a("## (d) New open owner questions (owner calls; not answered here)")
    a("")
    for q in d["new_open_questions"]:
        a(f"* **{q['id']}** {q['question']} Proposed: {q['proposed_answer']}. Needed by {q['needed_by']}.")
    a("")
    a("Remaining open items: " + _c(d["remaining_open_items"]))
    a("")
    a("## Scope deviations (declared)")
    a("")
    for x in d["scope_deviations"]:
        a(f"* **{x['id']}** {x['item']}: `{x['actual_path']}` instead of `{x['brief_path']}` (inside the allowed "
          f"paths: {x['within_allowed_paths']}); {x['reason']}; builder and Markdown at "
          f"{', '.join('`' + c + '`' for c in x['companion_files_at_brief_paths'])}; {x['status']}")
    a("")
    a("## (e) Historical reuse")
    a("")
    for x in d["historical_reuse"]["reused"]:
        a(f"* reused: {x}")
    for x in d["historical_reuse"]["not_reused"]:
        a(f"* not reused: {x}")
    a("")
    a("## (f) M16 impact")
    a("")
    a(f"{d['m16_impact']['file']}: {d['m16_impact']['note']}.")
    a("")
    a("## (g) H3 / H4 inputs")
    a("")
    for k, v in d["h3_h4_inputs"].items():
        for x in v:
            a(f"* {k.upper()}: {x}")
    a("")
    a("## Immutability")
    a("")
    a(f"{sum(1 for x in d['immutability'] if x['byte_identical_to_base'])} of {len(d['immutability'])} immutable / "
      f"historical files byte-identical to `{d['base_commit']}`.")
    a("")
    a("| path | what | sha256 | identical |")
    a("|---|---|---|---|")
    for x in d["immutability"]:
        a(f"| `{x['path']}` | {x['what']} | `{x['sha256']}` | {x['byte_identical_to_base']} |")
    a("")
    a("## Current pins (A9 deliverables after A9-10)")
    a("")
    a("| deliverable | path | sha256 | changed since base |")
    a("|---|---|---|---|")
    for x in d["current_pins"]:
        a(f"| {x['deliverable']} | `{x['path']}` | `{x['sha256']}` | {x['changed_since_base']} |")
    a("")
    a("## Authority pins")
    a("")
    for p_ in d["authority_pins"]:
        a(f"* `{p_['path']}` sha256 `{p_['sha256']}` - {p_['what']}")
    a("")
    a("Governance files are referenced, never pinned: " + ", ".join(f"`{g}`" for g in d["governance_files_not_pinned"]))
    a("")
    a("## Compliance")
    a("")
    for x in d["compliance"]:
        a(f"* {x}")
    return "\n".join(L) + "\n"


def dumps(doc) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify the outputs reproduce and every check passes")
    args = ap.parse_args(argv)
    doc, errors = build()
    js, md = dumps(doc), render_md(doc)
    jp, mp = os.path.join(ROOT, JSON_REL), os.path.join(ROOT, MD_REL)
    if errors:
        for e in errors[:60]:
            print("ERROR:", e)
    if args.check:
        ok = (not errors and os.path.isfile(jp) and open(jp, encoding="utf-8").read() == js
              and os.path.isfile(mp) and open(mp, encoding="utf-8").read() == md)
        print("OK" if ok else "DRIFT or FAILED CHECKS")
        return 0 if ok else 1
    with open(jp, "w", encoding="utf-8") as f:
        f.write(js)
    with open(mp, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {JSON_REL} and {MD_REL}" + (f" ({len(errors)} errors)" if errors else ""))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
