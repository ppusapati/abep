#!/usr/bin/env python3
"""A9.22 G8 stage 2: the record of the one controlled migration of the bus-boundary consumers from v1 to v2.

Owner decision A9.22 item 8 / G8_BUS_BOUNDARY: re-point every pinned consumer in one controlled migration, update the
pins together, keep v1 immutable and "verify that no physics result changes merely because the configuration
taxonomy changed". The stage-1 inventory (``CONSUMER_INVENTORY.json``) lists 28 LIVE_REPOINT files in 12 families.
This builder proves the migration from git alone. It compares the pre-migration commit ``PRE_COMMIT`` with the
migration commit ``POST_COMMIT`` (both fixed, so the record stays reproducible however the files move on later):

  * every LIVE_REPOINT file of the inventory changed in the migration (or is listed as deliberately unchanged);
  * every regenerated JSON output, diffed field by field (lists aligned by content / identity). Each changed leaf is
    classified. PIN_SHA, PATH, LABEL: the old value becomes the new one under the declared re-point substitutions
    (v1 -> v2 path / module / label / sha, and old -> new sha of every re-pointed file). PROVENANCE_TEXT: a declared
    provenance / citation text field. PROVENANCE_ADDED: an added record with no number in it. Any number that
    changes, appears or disappears is NUMERIC_CHANGE, and so is any other difference (UNEXPLAINED). Either one stops
    the build;
  * every regenerated Markdown rendering: each changed line carries the same numbers before and after (sha-like hex
    strings excluded);
  * the v1 family is byte-identical at both commits (immutable);
  * the v1 references that remain in the re-pointed files after the migration, each one matched to a declared
    retention reason (C1 ground-reference cells, carried history, historical reuse). An unmatched v1 reference stops
    the build.

    python docs/architecture_comparison/power_boundary_a9_v2/build_stage2_migration.py            # (re)write
    python docs/architecture_comparison/power_boundary_a9_v2/build_stage2_migration.py --check    # exit 1 on drift
    python docs/architecture_comparison/power_boundary_a9_v2/build_stage2_migration.py --preview  # POST = work tree
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT_JSON = os.path.join(HERE, "STAGE2_MIGRATION.json")
OUT_MD = os.path.join(HERE, "STAGE2_MIGRATION.md")
SCRIPT_REL = "docs/architecture_comparison/power_boundary_a9_v2/build_stage2_migration.py"
INVENTORY_REL = "docs/architecture_comparison/power_boundary_a9_v2/CONSUMER_INVENTORY.json"
DECISION = ("docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json G8_BUS_BOUNDARY (verbatim: "
            "docs/decisions/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md item 8)")
DATE = "2026-10-03"
PRE_COMMIT = "5b32edcc8e9124cd8bd12aba7d91204c1470aa3f"       # integration head before the migration
POST_COMMIT = "10aefa7ba6bf8d8fd78cae6fe8e38d32019bf417"     # the migration commit

V1_JSON = "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json"
V2_JSON = "docs/architecture_comparison/power_boundary_a9_v2/bus_power_boundary_a9_v2.json"
V1_MOD = "abep_sim/bus_boundary_a9.py"
V2_MOD = "abep_sim/bus_boundary_a9_v2.py"
V1_FAMILY = (V1_MOD, V1_JSON, "docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py",
             "docs/architecture_comparison/power_boundary_a9/BUS_POWER_BOUNDARY_A9.md",
             "schemas/interfaces/bus_power_boundary_a9_v1.json")

# recorded stage-2 order (inventory stage_2_rules): v2 artefact -> P1, P2, mass/power v3, Xe v3, RFQ v3, M16 v5, F7/F8
# -> RVM -> F9. (family, JSON outputs, Markdown renderings, regenerate command)
ORDER = [
    ("v2 artefact", [V2_JSON], ["docs/architecture_comparison/power_boundary_a9_v2/BUS_POWER_BOUNDARY_A9_V2.md"],
     "docs/architecture_comparison/power_boundary_a9_v2/build_bus_power_boundary_a9_v2.py"),
    ("P1 ICP bench", ["docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json"],
     ["docs/experiments/hall_icp/p1_icp_bench/P1_ICP_BENCH.md"],
     "docs/experiments/hall_icp/p1_icp_bench/build_p1_icp_bench.py"),
    ("P2 impedance prep", ["docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json"],
     ["docs/experiments/hall_icp/p2_impedance_map/P2_IMPEDANCE_PREP.md"],
     "docs/experiments/hall_icp/p2_impedance_map/build_p2_impedance_prep.py"),
    ("mass/power v3", ["docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json"],
     ["docs/budgets/mass_power_a9_v3/MASS_POWER_A9_V3.md"], "docs/budgets/mass_power_a9_v3/build_mass_power_a9_v3.py"),
    ("Xe accounting v3", ["docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json"],
     ["docs/budgets/xe_accounting_a9_v3/XE_ACCOUNTING_A9_V3.md"],
     "docs/budgets/xe_accounting_a9_v3/build_xe_accounting_a9_v3.py"),
    ("RFQ v3", ["docs/procurement/rfq_a9_v3/rfq_a9_v3.json"],
     ["docs/procurement/rfq_a9_v3/RFQ_A9_V3.md", "docs/procurement/rfq_a9_v3/packages/RFQ3-04_hall_electrical.md"],
     "docs/procurement/rfq_a9_v3/build_rfq_a9_v3.py"),
    ("M16 v5", ["docs/experiments/hall_icp/integration/m16_v5/subsystem_maturity_v5.json"],
     ["docs/experiments/hall_icp/integration/m16_v5/SUBSYSTEM_MATURITY_v5.md"],
     "docs/experiments/hall_icp/integration/m16_v5/build_subsystem_maturity_v5.py"),
    ("F7/F8 optimizer outputs", ["docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json",
                                 "docs/design_synthesis/f7_f8_optimizer/f7_upstream_pareto_v1.json",
                                 "docs/design_synthesis/f7_f8_optimizer/f8_robust_candidates_v1.json"],
     ["docs/design_synthesis/f7_f8_optimizer/F7_F8_OPTIMIZER.md"],
     "docs/design_synthesis/f7_f8_optimizer/build_f7_f8_optimizer.py"),
    ("RVM", ["docs/requirements/rvm_a9/rvm_a9_v1.json"], ["docs/requirements/rvm_a9/RVM_A9.md"],
     "docs/requirements/rvm_a9/build_rvm_a9.py"),
    ("F9 architecture freeze candidate", ["docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"],
     ["docs/architecture/freeze_candidate/ARCHITECTURE_FREEZE_CANDIDATE.md"],
     "docs/architecture/freeze_candidate/build_freeze_candidate.py"),
]
# LIVE_REPOINT files that need no edit (inventory: the scan matched them, but the v1 reference they carry is correct)
UNCHANGED_OK = {}

# declared provenance / citation text fields (output, JSON pointer regex, why); their text may change in any way
# that keeps every number (checked separately: the leaf is a string, never a number)
PROVENANCE_TEXT = [
    (V2_JSON, r"^/derived_from/consumers$", "consumer note: stage 1 -> stage 2 record"),
    ("docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json", r"^/authority_pins/\d+/role$", "pin role text"),
    ("docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json", r"^/deliverable_pins/\d+/what$",
     "pin role text"),
    ("docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json", r"^/power/peak_sampled_rule_v3/bus_boundary_module$",
     "module citation text"),
    ("docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json", r"^/items/\d+/(source|v3_change)$",
     "XV2-15 start-up template citation (I-S5 flight / C-S5 ground metadata) and its change note"),
    ("docs/procurement/rfq_a9_v3/rfq_a9_v3.json", r"^/packages/\d+/requirements/\d+/basis$",
     "RFQ2-HALLEL-R14 basis text: flight column v2, C1 ground-bench column v1"),
    ("docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json", r"^/referenced_not_pinned/\d+/use$",
     "module role text"),
    ("docs/requirements/rvm_a9/rvm_a9_v1.json", r"^/referenced_not_pinned/\d+/role$", "boundary role text"),
    ("docs/requirements/rvm_a9/rvm_a9_v1.json", r"^/rows/\d+/configurations/hall_icp_neutralizer/artifacts/\d+/detail/name$",
     "artifact name = boundary role text (flight cells only)"),
]
# v1 references that stay in re-pointed files after the migration: (file regex, line regex, reason)
RETAINED = [
    (r"\.(py|md|json)$", r"immutable|history|historical|v1 role text|stays v1|keep(s)? v1|kept|carried|C1 is not a v2|"
                         r"re-pointed (it|this helper) from|moved\s*$|BUS_V1|bus_power_boundary_a9_v1\"\)|"
                         r"PREDECESSOR|repointed_from|source_v2|BUS_V1_|_V1 = |V1_REL|carried_from_v2",
     "explicit history / re-point bookkeeping (the line names v1 as the predecessor, the carried history or the C1 "
     "retention)"),
    (r"build_mass_power_a9_v3\.py$", r"bus_boundary_a9 unchanged|BUS_MODULE_V1|\"7b23dbd2|A9.22 G8 re-point|"
                                      r"SEQUENCE_TEMPLATES \(PROPOSED",
     "mass/power v3: v1 module pinned as history of the carried v2 items and the retired C1 power configuration"),
    (r"mass_power_a9_v3\.json$", r".", "mass/power v3: carried v2 items (MPV2-P0x sources), retired C1 power "
                                       "configuration, v1 history pins (checked field by field below)"),
    (r"p1_icp_bench_v1\.json$|P1_ICP_BENCH\.md$|build_p1_icp_bench\.py$", r".",
     "P1: historical_reuse entry and its authority pin keep v1 (A902-19/21/22/23 definitions reused)"),
    (r"rfq_a9_v3\.json$", r".", "RFQ v3: C1 rows RFQ2-GAS-R26 / HALLEL-R22 / R25 / R29, the R14 C1 ground-bench column, "
                                "carried_from_v2.deliverable_pins and the repoint record keep v1"),
    (r"build_rfq_a9_v3\.py$", r".", "RFQ v3 builder: the re-point rule names the v1 document it replaces"),
    (r"rvm_a9_v1\.json$|RVM_A9\.md$|build_rvm_a9\.py$", r".",
     "RVM: hall_c1_reference ground-reference cells (RVM-19 / RVM-20) and the BUS_V1 reference keep v1"),
    (r"xe_accounting_a9_v3\.json$|XE_ACCOUNTING_A9_V3\.md$|build_xe_accounting_a9_v3\.py$", r".",
     "Xe v3: source_v2 (the v2-carried citation) and the builder's v1 -> v2 mapping"),
    (r"build_subsystem_maturity_v5\.py$", r".", "M16 v5: BUS_V1_REL (the v4-carried artifact text that is re-pointed)"),
    (r"test_single_flight_configuration\.py$", r".", "scan allowance for the byte-identical v1 document"),
    (r"test_mass_power_a9_v3\.py$", r".", "v1 module pin kept as history (carried v2 items)"),
    (r"test_rfq_a9_v3\.py$", r".", "test of the RFQ v3 citation-only re-point (C1 rows on v1)"),
]
# Markdown lines a rendering may gain: the pin / reference listings that now name both v2 and the retained v1
MD_ADDED_OK = (r"^- read, not pinned: `docs/architecture_comparison/power_boundary_a9(_v2)?/bus_power_boundary_a9_v[12]\.json`",
               r"^- `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1\.json` - `9f6e074c")
NAME_RX = re.compile(r"(?:bus_boundary_a9|bus_power_boundary_a9|power_boundary_a9|BUS_POWER_BOUNDARY_A9)(?!_v2|_V2)")
SHA_V1_RX = re.compile(r"7b23dbd23d39bd57|9f6e074cc2cdd1e2")
NUM_RX = re.compile(r"(?<![0-9A-Za-z_.])-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
HEX_RX = re.compile(r"\b[0-9a-f]{12,64}\b")
STAGE_RX = re.compile(r"\bstage [12]\b")      # "stage 1 / stage 2" of the migration in provenance text


class MigrationError(RuntimeError):
    """A physics value moved, an unexplained difference, or an unretained v1 reference (stop and report)."""


# ------------------------------------------------------------------------------------------------------ git access
def _git(*args: str) -> bytes:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if r.returncode:
        raise MigrationError(f"git {' '.join(args)}: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout


def read_at(commit: str, rel: str) -> bytes | None:
    if commit == "WORKTREE":
        p = os.path.join(ROOT, rel)
        return open(p, "rb").read() if os.path.isfile(p) else None
    r = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=ROOT, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def sha(b: bytes | None) -> str | None:
    return None if b is None else hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------------------------------------------ JSON diff
def _ident(x, subst):
    if not isinstance(x, dict):
        return None
    keys = tuple((k, subst(x[k]) if isinstance(x[k], str) else x[k])
                 for k in ("id", "path", "key", "pointer", "slot", "row", "symbol") if k in x)
    return keys or None


def diff(a, b, path, subst, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            if k in b:
                diff(a[k], b[k], f"{path}/{k}", subst, out)
            else:
                out.append({"path": f"{path}/{k}", "change": "REMOVED", "old": a[k], "new": None})
        for k in b:
            if k not in a:
                out.append({"path": f"{path}/{k}", "change": "ADDED", "old": None, "new": b[k]})
        return
    if isinstance(a, list) and isinstance(b, list):
        ka = [json.dumps(x, sort_keys=True) for x in a]
        kb = [json.dumps(x, sort_keys=True) for x in b]
        sm = difflib.SequenceMatcher(a=ka, b=kb, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            olds, news, pairs = list(range(i1, i2)), list(range(j1, j2)), []
            for i in list(olds):                       # pair by identity (v1 -> v2 substituted), then by position
                ia = _ident(a[i], subst)
                hits = [j for j in news if ia is not None and _ident(b[j], lambda t: t) == ia]
                if len(hits) == 1:
                    pairs.append((i, hits[0]))
                    olds.remove(i)
                    news.remove(hits[0])
            if len(olds) == len(news):
                pairs += list(zip(olds, news))
                olds, news = [], []
            for i, j in sorted(pairs, key=lambda p: p[1]):
                diff(a[i], b[j], f"{path}/{j}", subst, out)
            for i in olds:
                out.append({"path": f"{path}/{i}(before)", "change": "REMOVED", "old": a[i], "new": None})
            for j in news:
                out.append({"path": f"{path}/{j}", "change": "ADDED", "old": None, "new": b[j]})
        return
    if a != b:
        out.append({"path": path or "/", "change": "CHANGED", "old": a, "new": b})


def _has_number(o) -> bool:
    if isinstance(o, bool):
        return False
    if isinstance(o, (int, float)):
        return True
    if isinstance(o, dict):
        return any(_has_number(v) for v in o.values())
    if isinstance(o, list):
        return any(_has_number(v) for v in o)
    return False


def classify(rel: str, e: dict, subst) -> str:
    old, new = e["old"], e["new"]
    if e["change"] in ("ADDED", "REMOVED"):
        v = new if e["change"] == "ADDED" else old
        if _has_number(v):
            return "NUMERIC_CHANGE"
        return "PROVENANCE_ADDED" if e["change"] == "ADDED" else "UNEXPLAINED"
    if _has_number(old) or _has_number(new):
        return "NUMERIC_CHANGE"
    if isinstance(old, str) and isinstance(new, str):
        if subst(old) == new:
            if re.fullmatch(r"[0-9a-f]{64}", new):
                return "PIN_SHA"
            if old.replace("bus_power_boundary_a9_v1", "").replace("bus_boundary_a9.", "") != old and "/" not in new:
                return "LABEL"
            return "PATH" if "/" in new else "LABEL"
        for f, rx, _why in PROVENANCE_TEXT:            # declared non-physics citation / role text fields
            if f == rel and re.search(rx, e["path"]):
                return "PROVENANCE_TEXT"
    return "UNEXPLAINED"


# ---------------------------------------------------------------------------------------------------------- build
def build(post: str) -> dict:
    inv = json.loads(read_at(post, INVENTORY_REL))      # the stage-1 inventory as re-run at PRE_COMMIT
    if inv.get("base_commit") != PRE_COMMIT:
        raise MigrationError(f"inventory base commit {inv.get('base_commit')} != {PRE_COMMIT}")
    live = [c for c in inv["consumers"] if c["status"] == "LIVE_REPOINT"]
    transitive = [c for c in inv["consumers"] if c["status"] == "TRANSITIVE_LIVE"]
    retain = [c for c in inv["consumers"] if c["status"] == "LIVE_RETAIN_V1_REFERENCE"]
    immutable = [c for c in inv["consumers"] if c["status"] in ("IMMUTABLE_HISTORY", "SELF_V1", "GOVERNANCE_RECORD")]

    # ---- v1 family byte-identical
    v1 = []
    for rel in V1_FAMILY:
        a, b = sha(read_at(PRE_COMMIT, rel)), sha(read_at(post, rel))
        if a is None or a != b:
            raise MigrationError(f"v1 family file changed: {rel}")
        v1.append({"path": rel, "sha256": a})
    # ---- unchanged statuses really unchanged
    untouched = []
    for c in immutable + retain + transitive:
        if c["path"] == "docs/HISTORY.md":
            continue                                   # append-only log (gets the migration entry)
        a, b = sha(read_at(PRE_COMMIT, c["path"])), sha(read_at(post, c["path"]))
        if a != b:
            raise MigrationError(f"{c['status']} file changed in the migration: {c['path']}")
        untouched.append(c["path"])

    # ---- substitution map: v1 -> v2 identifiers, old -> new sha of every re-pointed / regenerated file
    pairs = [(V1_JSON, V2_JSON), (V1_MOD, V2_MOD), ("bus_power_boundary_a9_v1", "bus_power_boundary_a9_v2"),
             ("bus_boundary_a9.", "bus_boundary_a9_v2.")]
    shamap = {sha(read_at(PRE_COMMIT, V1_JSON)): sha(read_at(post, V2_JSON)),
              sha(read_at(PRE_COMMIT, V1_MOD)): sha(read_at(post, V2_MOD))}
    files = sorted({c["path"] for c in live} | {o for _f, js, mds, bld in ORDER for o in js + mds + [bld]}
                   | {"docs/budgets/mass_power_a9_v3/peak_sampled_gate_a9_v3.py"})
    for rel in files:
        a, b = sha(read_at(PRE_COMMIT, rel)), sha(read_at(post, rel))
        if a and b and a != b:
            shamap[a] = b

    def subst(s: str) -> str:
        for o, n in pairs:
            s = s.replace(o, n)
        for o, n in shamap.items():
            s = s.replace(o, n)
        return s.replace("bus_boundary_a9_v2_v2", "bus_boundary_a9_v2")

    # ---- per-output diffs, in the recorded order
    outputs, stop = [], []
    for fam, js, mds, bld in ORDER:
        for rel in js:
            ra, rb = read_at(PRE_COMMIT, rel), read_at(post, rel)
            ent = []
            diff(json.loads(ra), json.loads(rb), "", subst, ent)
            counts = {}
            for e in ent:
                e["class"] = classify(rel, e, subst)
                counts[e["class"]] = counts.get(e["class"], 0) + 1
                if e["class"] in ("NUMERIC_CHANGE", "UNEXPLAINED"):
                    stop.append(f"{rel} {e['path']}: {e['class']}")
            outputs.append({"family": fam, "path": rel, "kind": "json", "regenerated_by": bld,
                            "sha256_before": sha(ra), "sha256_after": sha(rb),
                            "byte_identical": sha(ra) == sha(rb), "class_counts": dict(sorted(counts.items())),
                            "changes": [{"path": e["path"], "change": e["change"], "class": e["class"],
                                         "before": _short(e["old"]), "after": _short(e["new"])} for e in ent]})
        for rel in mds:
            ra, rb = read_at(PRE_COMMIT, rel), read_at(post, rel)
            la, lb = ra.decode("utf-8").split("\n"), rb.decode("utf-8").split("\n")
            sm = difflib.SequenceMatcher(a=la, b=lb, autojunk=False)
            nlines, added, removed, same = 0, [], [], True
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    continue
                nlines += max(i2 - i1, j2 - j1)
                k = min(i2 - i1, j2 - j1)
                for x, y in zip(la[i1:i1 + k], lb[j1:j1 + k]):      # replaced lines: identical numbers
                    nx = sorted(NUM_RX.findall(STAGE_RX.sub("", HEX_RX.sub("", subst(x)))))
                    ny = sorted(NUM_RX.findall(STAGE_RX.sub("", HEX_RX.sub("", y))))
                    if nx != ny:
                        same = False
                        stop.append(f"{rel}: numbers differ in a changed line {nx} -> {ny}: {y[:120]}")
                added += lb[j1 + k:j2]
                removed += la[i1 + k:i2]
            for ln in added:                                       # inserted lines: declared listing lines only
                if not any(re.search(rx, ln) for rx in MD_ADDED_OK):
                    stop.append(f"{rel}: undeclared added line: {ln[:120]}")
            if removed:
                stop.append(f"{rel}: lines removed: {removed[:3]}")
            outputs.append({"family": fam, "path": rel, "kind": "markdown", "regenerated_by": bld,
                            "sha256_before": sha(ra), "sha256_after": sha(rb), "byte_identical": sha(ra) == sha(rb),
                            "changed_lines": nlines, "numbers_in_changed_lines_identical": same,
                            "added_listing_lines": added})
    # ---- every LIVE_REPOINT file changed (re-pointed) and its remaining v1 references are retained by reason
    repointed, remaining = [], []
    for c in live:
        a, b = sha(read_at(PRE_COMMIT, c["path"])), sha(read_at(post, c["path"]))
        if a == b and c["path"] not in UNCHANGED_OK:
            raise MigrationError(f"LIVE_REPOINT file not re-pointed: {c['path']}")
        repointed.append({"path": c["path"], "family": c["family"], "sha256_before": a, "sha256_after": b,
                          "v1_hits_before": len(c["hits"])})
        text = read_at(post, c["path"]).decode("utf-8").split("\n")
        hits = [(i + 1, ln.strip()) for i, ln in enumerate(text) if NAME_RX.search(ln) or SHA_V1_RX.search(ln)]
        for n, ln in hits:
            why = next((r for frx, lrx, r in RETAINED if re.search(frx, c["path"]) and re.search(lrx, ln)), None)
            if why is None:
                stop.append(f"{c['path']}:{n}: v1 reference not retained by a declared reason: {ln[:160]}")
            remaining.append({"path": c["path"], "line": n, "text": ln if len(ln) <= 200 else ln[:197] + "...",
                              "retained_because": why})
        repointed[-1]["v1_hits_after"] = len(hits)
    if stop:
        raise MigrationError("STOP - " + "; ".join(stop[:40]) + (f" (+{len(stop) - 40} more)" if len(stop) > 40 else ""))
    totals = {}
    for o in outputs:
        for k, v in o.get("class_counts", {}).items():
            totals[k] = totals.get(k, 0) + v
    return {
        "schema": "bus_boundary_stage2_migration_v1",
        "id": "bus_power_boundary_a9_v2_stage2_migration",
        "decision": DECISION,
        "stage": "2 (one controlled migration: every LIVE_REPOINT consumer re-pointed to bus_power_boundary_a9_v2)",
        "date": DATE, "pre_commit": PRE_COMMIT, "post_commit": post, "generated_by": SCRIPT_REL,
        "regenerate": f"python {SCRIPT_REL}  (check: --check)",
        "inventory": {"path": INVENTORY_REL, "base_commit": inv["base_commit"], "counts": inv["counts"]},
        "verdict": "NO_PHYSICS_RESULT_CHANGED: every changed field of every re-pointed output is a pin, path, label "
                   "or declared provenance text; no number changed, appeared or disappeared",
        "rules": [
            "v1 family byte-identical at both commits (A9.22 G8: v1 immutable)",
            "IMMUTABLE_HISTORY / SELF_V1 / GOVERNANCE_RECORD / LIVE_RETAIN_V1_REFERENCE / TRANSITIVE_LIVE files "
            "byte-identical (docs/HISTORY.md: append-only entry)",
            "every LIVE_REPOINT file changed; its remaining v1 references each carry a declared retention reason",
            "JSON outputs diffed field by field; NUMERIC_CHANGE or UNEXPLAINED stops the build",
            "Markdown renderings: the numbers in every changed line are identical before / after",
            "the v2 module runs the v1 code objects (tests/test_bus_boundary_a9_v2.py: a v2 hall_icp_neutralizer "
            "ledger / gate / allocation / start-up result equals v1 except the boundary label)",
            "C1 is not a v2 configuration: C1 ground-reference / retired cells keep citing v1"],
        "classes": {"PIN_SHA": "sha256 pin moved with the re-pointed file (old -> new sha)",
                    "PATH": "file path v1 -> v2 (document or module)",
                    "LABEL": "boundary label / module name v1 -> v2",
                    "PROVENANCE_TEXT": "declared citation / role text (no number changed)",
                    "PROVENANCE_ADDED": "added provenance record (pin, history note, re-point record; no number)",
                    "NUMERIC_CHANGE": "STOP", "UNEXPLAINED": "STOP"},
        "class_totals": dict(sorted(totals.items())),
        "order": [f for f, *_ in ORDER],
        "v1_family_byte_identical": v1,
        "repointed_consumers": repointed,
        "unchanged_by_status": {"count": len(untouched), "files": untouched},
        "transitive_live": [c["path"] for c in transitive],
        "live_retain_v1_reference": [c["path"] for c in retain],
        "outputs": outputs,
        "remaining_v1_references": remaining,
    }


def _short(v, n: int = 240):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, sort_keys=True)
    return s if len(s) <= n else s[:n - 3] + "..."


# ------------------------------------------------------------------------------------------------------ markdown
def render_md(d: dict) -> str:
    L = ["# Bus boundary v1 -> v2: stage-2 migration record (A9.22 G8)", "",
         f"<!-- GENERATED by {d['generated_by']} from STAGE2_MIGRATION.json; do not edit by hand -->", "",
         f"Decision: {d['decision']}. Pre-migration commit `{d['pre_commit']}`, migration commit "
         f"`{d['post_commit']}`. Inventory: `{d['inventory']['path']}` (base `{d['inventory']['base_commit']}`).", "",
         f"**Verdict: {d['verdict']}.**", "", "## Rules", ""]
    L += [f"- {r}" for r in d["rules"]]
    L += ["", "## Class totals", "", "| class | count | meaning |", "|---|---|---|"]
    L += [f"| {k} | {d['class_totals'].get(k, 0)} | {v} |" for k, v in d["classes"].items()]
    L += ["", "## Re-pointed consumers (LIVE_REPOINT)", "", "| file | family | v1 refs before | v1 refs after |",
          "|---|---|---|---|"]
    L += [f"| `{r['path']}` | {r['family']} | {r['v1_hits_before']} | {r['v1_hits_after']} |"
          for r in d["repointed_consumers"]]
    L += ["", "## Outputs (recorded order)", "", "| family | output | byte-identical | classes / check |",
          "|---|---|---|---|"]
    for o in d["outputs"]:
        cls = ", ".join(f"{k} {v}" for k, v in o["class_counts"].items()) if o["kind"] == "json" else \
            f"{o['changed_lines']} changed lines; numbers identical: {o['numbers_in_changed_lines_identical']}"
        L.append(f"| {o['family']} | `{o['path']}` | {o['byte_identical']} | {cls or '-'} |")
    L += ["", "## Field-level changes (JSON outputs)", "", "| output | field | change | class | before | after |",
          "|---|---|---|---|---|---|"]
    for o in d["outputs"]:
        for c in o.get("changes", []):
            L.append(f"| `{os.path.basename(o['path'])}` | `{c['path']}` | {c['change']} | {c['class']} | "
                     f"{_cell(c['before'])} | {_cell(c['after'])} |")
    L += ["", "## v1 references retained in re-pointed files", "", "| file | line | text | why |", "|---|---|---|---|"]
    L += [f"| `{r['path']}` | {r['line']} | {_cell(r['text'], 120)} | {r['retained_because']} |"
          for r in d["remaining_v1_references"]]
    L += ["", "## Unchanged by status", "",
          f"{d['unchanged_by_status']['count']} IMMUTABLE_HISTORY / SELF_V1 / GOVERNANCE_RECORD / "
          "LIVE_RETAIN_V1_REFERENCE / TRANSITIVE_LIVE files are byte-identical at both commits (docs/HISTORY.md "
          "excepted: append-only).", "",
          "LIVE_RETAIN_V1_REFERENCE (stay on v1): " + ", ".join(f"`{p}`" for p in d["live_retain_v1_reference"]) + ".",
          "", "v1 family (byte-identical): " + ", ".join(f"`{p['path']}`" for p in d["v1_family_byte_identical"]) + ".",
          ""]
    return "\n".join(L)


def _cell(v, n: int = 90) -> str:
    s = "-" if v is None else str(v)
    s = s.replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= n else s[:n - 3] + "..."


def outputs(post: str) -> dict:
    d = build(post)
    return {OUT_JSON: json.dumps(d, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_md(d)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--preview", action="store_true", help="compare against the working tree (nothing written)")
    a = ap.parse_args(argv)
    if a.preview:
        d = build("WORKTREE")
        print(json.dumps({"class_totals": d["class_totals"], "outputs": [
            (o["path"], o.get("class_counts") or o.get("numbers_in_changed_lines_identical")) for o in d["outputs"]],
            "remaining": len(d["remaining_v1_references"])}, indent=1))
        return 0
    if POST_COMMIT.startswith("MIGRATION_COMMIT"):
        print("POST_COMMIT not set (use --preview before the migration commit exists)", file=sys.stderr)
        return 2
    outs = outputs(POST_COMMIT)
    if a.check:
        bad = [p for p, t in outs.items() if not os.path.isfile(p) or open(p, encoding="utf-8").read() != t]
        if bad:
            print("DRIFT: " + ", ".join(os.path.relpath(p, ROOT) for p in bad))
            return 1
        print("OK")
        return 0
    for p, t in outs.items():
        with open(p, "w", encoding="utf-8") as f:
            f.write(t)
    print("wrote " + ", ".join(os.path.relpath(p, ROOT) for p in outs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
