"""Architecture decision-dossier generator (scripts/architecture/build_decision_dossier.py, lane_27_decision_dossier).

Runs on the repository and on SYNTHETIC temporary roots (copies of a few repository files, plus a SYNTHETIC owner
record that exists only in a temporary directory). No other lane's files are required: inputs that are absent must
appear as UNRESOLVED, never as values.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "architecture", "build_decision_dossier.py")
TS = "2026-01-01T00:00:00Z"

_spec = importlib.util.spec_from_file_location("build_decision_dossier", SCRIPT)
dd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dd)


@pytest.fixture(scope="module")
def repo_dossier():
    return dd.build(ROOT, generated_at=TS)


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def _copy(rel, dst_root):
    dst = os.path.join(dst_root, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, rel), dst)


# ---------------------------------------------------------------------------------------------------------------------
def test_runs_on_repository(repo_dossier):
    d = repo_dossier
    assert d["schema"] == dd.DOSSIER_SCHEMA and d["nature"] == "STATUS_NOT_A_DECISION"
    assert list(d["architectures"]) == list(dd.ARCHITECTURES)
    for arch, a in d["architectures"].items():
        if isinstance(a["hard_gates"], list):
            for g in a["hard_gates"]:
                assert g["verdict"] in ("PASS", "FAIL", "UNDETERMINED")
            # elimination only through the hard-gate logic: a binding FAIL recorded as elimination basis
            binding_fail = [g["gate"] for g in a["hard_gates"] if g["binding"] and g["verdict"] == "FAIL"]
            assert a["eliminated"] == bool(binding_fail) == bool(a["elimination_basis"])
            ms = a["milestones"]
            assert ms["currently_reachable"]
            if ms["currently_reachable"].startswith("A"):
                assert ms["A"]["hard_gate_conditions"], "a conditional A statement must list its conditions"
                assert ms["next_milestone"] == "B" and ms["missing_for_next"]
        assert "top_unresolved_nodes" in a["failure_tree"] or a["failure_tree"]["state"] == "UNRESOLVED"


def test_hard_gate_section_matches_committed_status(repo_dossier):
    hgl = repo_dossier["hard_gate_logic"]
    if hgl.get("state") != "RESOLVED":
        pytest.skip("hard-gate files not present")
    assert hgl["committed_status_consistency"] in ("CURRENT", "STALE_COMMITTED_STATUS")
    with open(os.path.join(ROOT, dd.F["status"]), encoding="utf-8") as f:
        committed = json.load(f)
    assert hgl["eliminated"] == committed["eliminated"]


def test_missing_inputs_are_unresolved_on_repository(repo_dossier):
    d = repo_dossier
    unresolved = {u["key"]: u for u in d["unresolved_inputs"]}
    for row in d["inputs"]:
        absent = row["state"] in ("UNRESOLVED", "PARTIAL")
        assert absent == (row["key"] in unresolved)
        if absent:
            assert unresolved[row["key"]]["lane"] == row["lane"] and unresolved[row["key"]]["reason"]
    if not os.path.isdir(os.path.join(ROOT, "docs", "milestones", "bundle1")):
        b = unresolved["bundle1"]
        assert b["lane"] == "fo_bundle1_conditional_selection" and "not anticipated" in b["reason"]
    if not os.path.isfile(os.path.join(ROOT, dd.OWNER_DECISION_RECORD)):
        assert "owner_decision_record" in unresolved


def test_synthetic_root_lists_everything_missing_as_unresolved(tmp_path):
    root = str(tmp_path)
    _copy("CLAUDE.md", root)
    d = dd.build(root, generated_at=TS)
    keys = {u["key"] for u in d["unresolved_inputs"]}
    assert keys == {s["key"] for s in dd.INPUTS} - {"claude_md"}
    for u in d["unresolved_inputs"]:
        assert u["lane"] and u["missing"]
    assert d["hard_gate_logic"]["state"] == "UNRESOLVED"
    for a in d["architectures"].values():
        assert a["eliminated"] is None and a["hard_gates"]["state"] == "UNRESOLVED"
        assert a["failure_tree"]["state"] == "UNRESOLVED"
    assert d["decision"]["selected_architecture"] is None
    assert set(d["provenance"]["input_files_sha256"]) == {"CLAUDE.md"}
    assert "UNRESOLVED" in dd.render_md(d)


def test_provenance_hashes_are_correct(repo_dossier):
    pv = repo_dossier["provenance"]
    assert pv["input_files_sha256"]
    for rel, h in pv["input_files_sha256"].items():
        assert _sha(os.path.join(ROOT, rel)) == h, rel
    for row in repo_dossier["inputs"]:
        for rel in row["files"]:
            assert rel in pv["input_files_sha256"], rel
    assert pv["generator_sha256"][dd.GENERATOR] == _sha(SCRIPT)
    assert pv["generation"]["generated_at"] == TS
    assert pv["deterministic_except"] == ["provenance.generation.generated_at"]


def test_no_winner_output(repo_dossier):
    d = repo_dossier
    assert d["decision"]["decision_status"] == "STATUS_NOT_A_DECISION"
    assert d["decision"]["selected_architecture"] is None
    assert "STATUS, not a decision" in d["decision"]["statement"]
    assert not any("winner" in k.lower() for k in _keys(d))
    md = dd.render_md(d)
    assert "winner" not in md.lower()
    assert "status, not a decision" in md.lower()


def test_owner_record_alone_never_selects(tmp_path):
    """A SYNTHETIC owner record without gate eliminations must not make the dossier name an architecture."""
    root = str(tmp_path)
    for rel in ("CLAUDE.md", dd.F["matrix"], dd.F["register"], dd.F["status"]):
        _copy(rel, root)
    rec = os.path.join(root, dd.OWNER_DECISION_RECORD)
    os.makedirs(os.path.dirname(rec), exist_ok=True)
    with open(rec, "w", encoding="utf-8") as f:
        json.dump({"decided_by": "SYNTHETIC test fixture", "architecture": "rf_hall", "milestone": "A"}, f)
    d = dd.build(root, generated_at=TS)
    assert d["hard_gate_logic"]["state"] == "RESOLVED"
    assert d["decision"]["owner_decision_record"]["state"] == "PRESENT"
    assert d["decision"]["selected_architecture"] is None
    assert d["decision"]["decision_status"] == "STATUS_NOT_A_DECISION"
    assert len(d["decision"]["not_eliminated"]) == 3


def test_deterministic(tmp_path, repo_dossier):
    d2 = dd.build(ROOT, generated_at=TS)
    assert dd.dump_json(repo_dossier) == dd.dump_json(d2)
    assert dd.render_md(repo_dossier) == dd.render_md(d2)
    a, b = tmp_path / "a", tmp_path / "b"
    dd.write(repo_dossier, str(a))
    dd.write(d2, str(b))
    for name in (dd.JSON_NAME, dd.MD_NAME):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    d3 = dd.build(ROOT, generated_at="2030-01-01T00:00:00Z")
    strip = lambda x: {k: v for k, v in dd._without_generation(x).items()}   # noqa: E731
    assert strip(d3) == strip(repo_dossier)


def test_committed_dossier_is_well_formed():
    jp = os.path.join(ROOT, dd.OUT_DIR_REL, dd.JSON_NAME)
    mp = os.path.join(ROOT, dd.OUT_DIR_REL, dd.MD_NAME)
    assert os.path.isfile(jp) and os.path.isfile(mp)
    with open(jp, encoding="utf-8") as f:
        d = json.load(f)
    assert d["nature"] == "STATUS_NOT_A_DECISION" and d["decision"]["selected_architecture"] is None
    assert all(len(h) == 64 for h in d["provenance"]["input_files_sha256"].values())
    with open(mp, encoding="utf-8") as f:
        assert "winner" not in f.read().lower()
