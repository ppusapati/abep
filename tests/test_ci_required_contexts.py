"""Required status-check contexts for `main` (docs/ci/BRANCH_PROTECTION.md, owner decision 2026-09-27).

GitHub reports one status-check context per workflow job (per matrix leg for a matrix job), named by the job's `name:`
after `${{ matrix.* }}` substitution. The branch-protection specification lists the contexts the owner makes required.
These tests assert that the documented list equals the contexts `.github/workflows/ci.yml` actually produces, exactly,
so that renaming a job or changing a matrix value cannot silently orphan a required check. Repository governance only:
no physics, data or scientific outcome is read.
"""
from __future__ import annotations

import itertools
import os
import re

import yaml  # PyYAML is locked (requirements-lock.txt); imported directly so a missing dep fails, never adds a skip (rule 9).

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CI_YML = os.path.join(ROOT, ".github", "workflows", "ci.yml")
SMOKE_YML = os.path.join(ROOT, ".github", "workflows", "julia-smoke.yml")
SPEC_MD = os.path.join(ROOT, "docs", "ci", "BRANCH_PROTECTION.md")

BLOCK_RE = re.compile(r"^```required-status-checks[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
MATRIX_EXPR_RE = re.compile(r"\$\{\{\s*matrix\.([A-Za-z0-9_-]+)\s*\}\}")
ANY_EXPR_RE = re.compile(r"\$\{\{.*?\}\}")


def _load_workflow(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        wf = yaml.safe_load(fh)
    # YAML 1.1 reads the bare key `on` as boolean True.
    if True in wf and "on" not in wf:
        wf["on"] = wf.pop(True)
    return wf


def _job_contexts(job_id: str, job: dict) -> list[str]:
    """Contexts GitHub reports for one job: its name (job id if unnamed) expanded over the matrix."""
    name = job.get("name", job_id)
    matrix = (job.get("strategy") or {}).get("matrix")
    if matrix is None:
        assert not ANY_EXPR_RE.search(name), f"job {job_id!r}: expression in name without a matrix: {name!r}"
        return [name]
    assert isinstance(matrix, dict), f"job {job_id!r}: dynamic matrix ({matrix!r}) cannot be pinned as required checks"
    unsupported = {"include", "exclude"} & set(matrix)
    assert not unsupported, (f"job {job_id!r}: matrix {sorted(unsupported)} not handled by this test; extend it and "
                             "docs/ci/BRANCH_PROTECTION.md together")
    for key, values in matrix.items():
        assert isinstance(values, list) and values, f"job {job_id!r}: matrix.{key} must be a literal non-empty list"
    used = MATRIX_EXPR_RE.findall(name)
    assert set(used) == set(matrix), (f"job {job_id!r}: name {name!r} must reference every matrix key {sorted(matrix)} "
                                      "or two legs report the same context")
    keys = list(matrix)
    out = []
    for combo in itertools.product(*(matrix[k] for k in keys)):
        values = dict(zip(keys, combo))
        expanded = MATRIX_EXPR_RE.sub(lambda m: str(values[m.group(1)]), name)
        assert not ANY_EXPR_RE.search(expanded), f"job {job_id!r}: unexpanded expression in {expanded!r}"
        out.append(expanded)
    return out


def _workflow_contexts(path: str) -> list[str]:
    wf = _load_workflow(path)
    return [c for jid, job in wf["jobs"].items() for c in _job_contexts(jid, job)]


def _documented_contexts() -> list[str]:
    with open(SPEC_MD, encoding="utf-8") as fh:
        text = fh.read()
    blocks = BLOCK_RE.findall(text)
    assert len(blocks) == 1, f"expected exactly one ```required-status-checks block in {SPEC_MD}, found {len(blocks)}"
    lines = blocks[0].splitlines()
    assert all(ln == ln.strip() and ln for ln in lines), "one context per line, no blank lines or surrounding spaces"
    return lines


def test_documented_contexts_equal_ci_job_names_times_matrix():
    documented = _documented_contexts()
    produced = _workflow_contexts(CI_YML)
    assert len(documented) == len(set(documented)), f"duplicate documented context: {documented}"
    assert len(produced) == len(set(produced)), f"two ci.yml jobs/legs report the same context: {produced}"
    assert set(documented) == set(produced), (
        "docs/ci/BRANCH_PROTECTION.md required contexts differ from ci.yml:\n"
        f"  documented only: {sorted(set(documented) - set(produced))}\n"
        f"  ci.yml only:     {sorted(set(produced) - set(documented))}\n"
        "Update the spec (and the GitHub setting, BRANCH_PROTECTION.md sections 4-6) in the same change.")


def test_expected_contexts_literal():
    # Pins the owner-decided set literally, so a coordinated rename of ci.yml + spec is still a visible diff here.
    assert sorted(_documented_contexts()) == sorted([
        "Repository integrity (scripts/ci_checks.py)",
        "Tests + golden benchmarks (pymsis present)",
        "Tests + golden benchmarks (pymsis absent)",
    ])


def test_required_jobs_report_on_every_pull_request():
    wf = _load_workflow(CI_YML)
    on = wf["on"]
    assert isinstance(on, dict) and "pull_request" in on, "ci.yml must trigger on pull_request"
    pr = on["pull_request"] or {}
    for key in ("paths", "paths-ignore", "branches-ignore"):
        assert key not in pr, f"pull_request.{key} can leave a required context unreported"
    if "branches" in pr:
        assert "main" in pr["branches"], "pull_request.branches must include main"
    for jid, job in wf["jobs"].items():
        assert "if" not in job, f"job {jid!r} has a job-level if:; a skipped required job does not gate the merge"


def test_manual_smoke_workflow_is_not_required():
    wf = _load_workflow(SMOKE_YML)
    triggers = set(wf["on"]) if isinstance(wf["on"], dict) else {wf["on"]} if isinstance(wf["on"], str) else set(wf["on"])
    assert triggers == {"workflow_dispatch"}, f"julia-smoke.yml must stay manual-only, has {sorted(triggers)}"
    smoke = set(_workflow_contexts(SMOKE_YML))
    assert not smoke & set(_documented_contexts()), f"manual smoke context listed as required: {smoke}"


def test_no_other_workflows_unaccounted_for():
    wf_dir = os.path.dirname(CI_YML)
    found = sorted(f for f in os.listdir(wf_dir) if f.endswith((".yml", ".yaml")))
    assert found == ["ci.yml", "julia-smoke.yml"], (
        f"new workflow(s) {found}: decide (owner) whether they are required and update docs/ci/BRANCH_PROTECTION.md")
