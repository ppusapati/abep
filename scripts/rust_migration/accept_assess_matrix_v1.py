"""Acceptance run of ACCEPT-NI-ABEP-ASSESS-RFP-MATRIX-V1 (SC-WP-11): the RFP constraint matrix and the HC-05 evaluator.

  python scripts/rust_migration/accept_assess_matrix_v1.py

Runs the registered acceptance cases (cargo tests of crates/abep-assess: AC-01..AC-04, AC-06..AC-10 in
tests/matrix_acceptance.rs, AC-05 in tests/crate_graph.rs), produces the matrix record on today's admitted raw results
twice with `abep-assess-matrix` (byte identity), and writes acceptance_report_v1.json / .md and
rfp_constraint_matrix_run_v1.json next to the acceptance prereg. Tooling only: no Python reference is involved.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADIR = ROOT / "docs/rust_migration/contracts/NI-ABEP-ASSESS-RFP-MATRIX"
PREREG = ADIR / "acceptance_v1.json"
CASES = {"AC-01": "ac01_four_separate_fields_and_no_assessment_word_in_raw",
         "AC-02": "ac02_threshold_change_moves_assessment_never_raw_physics",
         "AC-03": "ac03_todays_raw_results_are_fail_closed", "AC-04": "ac04_hc05_rule_order",
         "AC-05": "no_physics_crate_depends_on_abep_assess", "AC-06": "ac06_no_requirement_parsing_in_raw_physics",
         "AC-07": "ac07_ac08_deterministic_and_raw_unchanged", "AC-08": "ac07_ac08_deterministic_and_raw_unchanged",
         "AC-09": "ac09_non_determining_records_never_comply", "AC-10": "ac10_tampered_records_fail_closed"}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def main() -> int:
    prereg = json.loads(PREREG.read_text())
    env = dict(os.environ, PATH=f"/root/.cargo/bin:{os.environ.get('PATH', '')}", CARGO_INCREMENTAL="0")
    manifest = sha((ROOT / "config/MANIFEST.json").read_bytes())
    want = re.search(r"different from ([0-9a-f]{64})", prereg["decision_rules"]["input_mismatch"]).group(1)
    if manifest != want:
        print("NOT_RUN_INPUT_MISMATCH")
        return 3
    t = subprocess.run(["cargo", "test", "--release", "--locked", "-p", "abep-assess", "--test", "matrix_acceptance",
                        "--test", "crate_graph", "--", "--test-threads=1"], cwd=ROOT, env=env, capture_output=True,
                       text=True)
    results = dict(re.findall(r"^test (\w+) \.\.\. (ok|FAILED)$", t.stdout, flags=re.M))
    cases = {k: {"test": v, "result": results.get(v, "NOT_RUN")} for k, v in CASES.items()}
    subprocess.run(["cargo", "build", "--release", "--locked", "-p", "abep-assess", "--bin", "abep-assess-matrix"],
                   cwd=ROOT, env=env, check=True, capture_output=True)
    binary = ROOT / "target/release/abep-assess-matrix"
    with tempfile.TemporaryDirectory() as d:
        outs = []
        for i in range(2):
            p = Path(d) / f"m{i}.json"
            subprocess.run([str(binary), "--repo", str(ROOT), "--out", str(p)], check=True, env=env)
            outs.append(p.read_bytes())
    identical = outs[0] == outs[1]
    (ADIR / "rfp_constraint_matrix_run_v1.json").write_bytes(outs[0])
    m = json.loads(outs[0])
    accepted = all(c["result"] == "ok" for c in cases.values()) and identical and t.returncode == 0
    rustc = subprocess.run(["/root/.cargo/bin/rustc", "--version"], capture_output=True, text=True).stdout.strip()
    src = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted((ROOT / "crates/abep-assess").rglob("*"))
           if p.is_file()}
    rows = [{"id": r["id"], "raw_status": r["raw_physics_result"].get("status"),
             "evidence_status": r["evidence_status"]["status"], "rfp_assessment_status": r["rfp_assessment_status"]["status"],
             "basis": r["rfp_assessment_status"].get("basis")} for r in m["rows"]]
    rep = {
        "schema": "abep_new_infrastructure_acceptance_report_v1",
        "id": "ACCEPT-NI-ABEP-ASSESS-RFP-MATRIX-V1-REPORT",
        "acceptance": {"path": str(PREREG.relative_to(ROOT)), "sha256": sha(PREREG.read_bytes()),
                       "registered_in_commit": git("log", "--diff-filter=A", "--format=%H", "--",
                                                   str(PREREG.relative_to(ROOT))).splitlines()[-1]},
        "verdict": "ACCEPTED" if accepted else "NOT_ACCEPTED",
        "head": git("rev-parse", "HEAD"), "git_dirty": git("status", "--porcelain").splitlines(),
        "rustc": rustc, "binary_sha256": sha(binary.read_bytes()), "source_sha256": src,
        "config_manifest_sha256": manifest,
        "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "cases": cases, "matrix_runs_byte_identical": identical,
        "campaign_history": [
            {"execution": 1, "outcome": "ABORTED_BEFORE_REPORT",
             "detail": "the shared filesystem ran out of space (ENOSPC): the second abep-assess-matrix write failed "
                       "(exit 101) after the cargo tests; no report or record was written; nothing was changed "
                       "afterwards except running the tests in the release profile (disk headroom)"},
            {"execution": 2, "outcome": "THIS_REPORT"}],
        "matrix_record": {"path": str((ADIR / "rfp_constraint_matrix_run_v1.json").relative_to(ROOT)),
                          "sha256": sha(outs[0])},
        "matrix_summary": {"rows": rows, "assessment_status_counts": m["assessment_status_counts"],
                           "HC-05": m["engineering_gates"]["HC-05"]["status"],
                           "GNG-ICP-01": m["engineering_gates"]["rvm_and_icp_gate"]["GNG-ICP-01"]["status"],
                           "rvm_replay": m["engineering_gates"]["rvm_and_icp_gate"]["rvm_replay"]},
        "ledger_update_requested": [{"component": "NI-ABEP-ASSESS-RFP-MATRIX", "request":
                                     "ACCEPTED (lifecycle PREREG_ACCEPTANCE -> RUST_IMPL -> ACCEPTED) on this report; "
                                     "crate crates/abep-assess (abep_assess::{matrix, neutralization::hc05}); ADMITTED "
                                     "additionally needs the workspace CI run of the acceptance tests"
                                     if accepted else "NONE (not accepted)"}],
        "what_this_is_not": prereg["what_this_is_not"],
    }
    (ADIR / "acceptance_report_v1.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n",
                                                     encoding="utf-8")
    L = ["# Acceptance report v1 - ACCEPT-NI-ABEP-ASSESS-RFP-MATRIX-V1", "",
         f"Verdict: **{rep['verdict']}**. Generated from `acceptance_report_v1.json`.", "",
         f"* Prereg sha256 `{rep['acceptance']['sha256']}` (commit `{rep['acceptance']['registered_in_commit'][:12]}`); "
         f"HEAD `{rep['head'][:12]}`; {rustc}.",
         f"* Matrix record `{rep['matrix_record']['path']}` sha256 `{rep['matrix_record']['sha256']}`; two runs "
         f"byte-identical: {identical}.", "", "## Cases", ""]
    for k, c in cases.items():
        L.append(f"* {k} ({c['test']}): {c['result']}")
    L += ["", "## The matrix on today's admitted raw results", "",
          "| requirement | raw physics | evidence | RFP assessment |", "|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['id']} | {r['raw_status']} | {r['evidence_status']} | {r['rfp_assessment_status']} |")
    L += ["", f"HC-05: {rep['matrix_summary']['HC-05']}; GNG-ICP-01: {rep['matrix_summary']['GNG-ICP-01']}; RVM replay "
          f"{rep['matrix_summary']['rvm_replay']['reproduce_committed']} / {rep['matrix_summary']['rvm_replay']['cells']} "
          "cells reproduced.", "", "## Ledger update requested", ""]
    L += [f"* {x['component']}: {x['request']}" for x in rep["ledger_update_requested"]]
    L += ["", "Not an architecture verdict and not a relabelling of any raw status.", ""]
    (ADIR / "acceptance_report_v1.md").write_text("\n".join(L), encoding="utf-8")
    print(rep["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
