"""Optional Rust CI for abep_core (.github/workflows/rust-parity.yml; docs/ci/RUST_PARITY.md).

Owner decision A9.14 S10.4 (RUST-OQ-02, OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES;
docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md, json sha256 c6c00b7f...). Structural checks of the workflow
(triggers, steps, conditions, pins, no secrets, not a required context) plus the non-interactive CLI entry points of
scripts/verify_abep_core.py exercised without a Rust toolchain. Never skips (CLAUDE.md rule 9). No Rust, no campaign.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re

import pytest
import yaml  # PyYAML is locked (requirements-lock.txt); imported directly so a missing dep fails, never adds a skip.

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows", "rust-parity.yml")
CI_YML = os.path.join(ROOT, ".github", "workflows", "ci.yml")
REPORT = os.path.join(ROOT, "docs", "performance", "abep_core", "parity_report_v1.json")
DOC = os.path.join(ROOT, "docs", "ci", "RUST_PARITY.md")
OD_JSON = os.path.join(ROOT, "docs", "decisions", "OD_2026_10_01_A9_14_s7_s10_owner_decisions.json")
OD_JSON_SHA256 = "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c"

WATCHED_PATHS = {"abep_core/**", "abep_sim/design/tpmc_backend.py", "abep_sim/intake_tpmc.py",
                 "scripts/verify_abep_core.py", "docs/performance/abep_core/**", ".github/workflows/rust-parity.yml"}
ALLOWED_ACTIONS = {"actions/checkout@v4", "actions/setup-python@v5", "actions/upload-artifact@v4"}
CHANGED = "steps.src.outputs.sources_match_recorded_build != 'true'"
UNCHANGED = "steps.src.outputs.sources_match_recorded_build == 'true'"


def _load(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    doc = yaml.safe_load(text)
    if True in doc and "on" not in doc:                    # YAML 1.1 reads a bare `on` key as True
        doc["on"] = doc.pop(True)
    return doc, text


def _steps():
    doc, _ = _load(WF)
    assert list(doc["jobs"]) == ["parity"]
    return doc["jobs"]["parity"]["steps"]


def _step(name_part):
    hits = [s for s in _steps() if name_part in s.get("name", "")]
    assert len(hits) == 1, (name_part, [s.get("name") for s in hits])
    return hits[0]


def _verify():
    spec = importlib.util.spec_from_file_location("verify_abep_core_ci", os.path.join(ROOT, "scripts/verify_abep_core.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------------------------------ triggers
def test_triggers_paths_and_dispatch():
    doc, _ = _load(WF)
    on = doc["on"]
    assert set(on) == {"push", "pull_request", "workflow_dispatch"}
    assert "pull_request_target" not in on
    assert set(on["push"]["paths"]) == WATCHED_PATHS and set(on["pull_request"]["paths"]) == WATCHED_PATHS
    ci, _ = _load(CI_YML)
    assert on["push"]["branches"] == ci["on"]["push"]["branches"]      # same branches as ci.yml


def test_watched_paths_cover_every_provenance_source():
    V = _verify()
    for src in V.PROVENANCE_SOURCES:
        assert src in WATCHED_PATHS or (src.startswith("abep_core/") and "abep_core/**" in WATCHED_PATHS), src


# --------------------------------------------------------------------------------------- permissions / secrets / pins
def test_no_secrets_and_read_only():
    doc, text = _load(WF)
    assert doc["permissions"] == {"contents": "read"}
    assert "permissions" not in doc["jobs"]["parity"]
    assert "secrets." not in text and "GITHUB_TOKEN" not in text and "github.token" not in text
    for forbidden in ("git push", "git commit", "curl ", "wget "):
        assert forbidden not in text, forbidden
    assert "continue-on-error" not in text


def test_only_pinned_wellknown_actions():
    used = {s["uses"] for s in _steps() if "uses" in s}
    assert used <= ALLOWED_ACTIONS, used
    assert {"actions/checkout@v4", "actions/setup-python@v5"} <= used


def test_toolchain_and_python_pins_match_the_record():
    doc, _ = _load(WF)
    ci, _ = _load(CI_YML)
    rep = json.load(open(REPORT))
    rustc = rep["build_provenance"]["rustc"]
    assert rustc.startswith(f"rustc {doc['env']['RUST_TOOLCHAIN']} "), rustc
    assert doc["env"]["PYTHON_VERSION"] == ci["env"]["PYTHON_VERSION"] == "3.11"
    assert rep["build_provenance"]["python"].startswith("3.11.")
    assert re.fullmatch(r"\d+\.\d+\.\d+", doc["env"]["MATURIN_VERSION"])
    tool = _step("Install the pinned Rust toolchain")["run"]
    assert 'rustup toolchain install "$RUST_TOOLCHAIN"' in tool and 'rustup default "$RUST_TOOLCHAIN"' in tool
    assert "build_provenance" in _step("Toolchain equals the recorded build toolchain")["run"]
    build = _step("Build abep_core into a scratch venv")["run"]
    assert '"maturin==$MATURIN_VERSION"' in build and "maturin develop --release --locked" in build
    assert "--system-site-packages" in build and "$RUNNER_TEMP/venv_rust" in build
    assert _step("Pure-Rust unit tests")["run"] == "cargo test --release --locked"


# --------------------------------------------------------------------------------------------- step logic
def test_step_order_and_conditions():
    names = [s.get("name", s.get("uses")) for s in _steps()]
    order = ["Sources vs the recorded build", "Refuse a changed Python reference", "Parity record check",
             "Install the pinned Rust toolchain", "Pure-Rust unit tests", "Build abep_core", "Extension state",
             "Parity suite", "Bitwise reproduction", "FULL pre-registered parity campaign", "Upload the campaign report",
             "Campaign re-admits every kernel"]
    idx = [next(i for i, n in enumerate(names) if o in n) for o in order]
    assert idx == sorted(idx), names

    assert "--source-status --github-output \"$GITHUB_OUTPUT\"" in _step("Sources vs the recorded build")["run"]
    assert _step("Sources vs the recorded build")["id"] == "src"
    ref = _step("Refuse a changed Python reference")
    assert ref["if"] == "steps.src.outputs.reference_matches_prereg != 'true'" and "exit 1" in ref["run"]
    rec = _step("Parity record check")
    assert rec["if"] == UNCHANGED and rec["run"] == "python scripts/verify_abep_core.py --check"
    suite = _step("Parity suite")
    assert "if" not in suite and suite["run"].endswith("scripts/verify_abep_core.py --dev --strict")
    bit = _step("Bitwise reproduction")
    assert UNCHANGED in bit["if"] and "extension_is_recorded_build == 'true'" in bit["if"]
    assert bit["run"].endswith("--check --recompute 3")


def test_full_campaign_runs_only_on_changed_sources_and_must_readmit():
    camp = _step("FULL pre-registered parity campaign")
    assert camp["id"] == "campaign" and camp["if"] == CHANGED
    assert camp["run"].strip("'").endswith("scripts/verify_abep_core.py")      # the scoring campaign: no flags
    up = _step("Upload the campaign report")
    assert up["uses"] == "actions/upload-artifact@v4"
    assert up["if"] == "always() && steps.campaign.conclusion != 'skipped'"     # uploaded whatever the verdict
    assert "parity_report_v1.json" in up["with"]["path"] and "parity_report_v1.md" in up["with"]["path"]
    assert up["with"]["if-no-files-found"] == "error"
    gate = _step("Campaign re-admits every kernel")
    assert gate["if"] == CHANGED
    assert "--check" in gate["run"] and 'x == "ADMITTED"' in gate["run"] and "sys.exit(" in gate["run"]


def test_campaign_never_runs_with_the_development_seed_and_dev_never_scores():
    runs = [s.get("run", "") for s in _steps()]
    dev = [r for r in runs if "--dev" in r]
    assert len(dev) == 1 and "--strict" in dev[0] and "--only" not in dev[0] and "--limit" not in dev[0]
    assert not any("--render-md" in r for r in runs)                          # CI never re-renders the record


# ------------------------------------------------------------------------------------- optional, not required
def test_optional_not_a_required_context():
    doc, _ = _load(WF)
    name = doc["jobs"]["parity"]["name"]
    assert "optional" in name
    bp = open(os.path.join(ROOT, "docs", "ci", "BRANCH_PROTECTION.md"), encoding="utf-8").read()
    blocks = re.findall(r"^```required-status-checks[ \t]*\n(.*?)^```[ \t]*$", bp, re.M | re.S)
    assert len(blocks) == 1 and name not in blocks[0]                    # never a required status-check context
    assert "rust-parity.yml" in bp and "S10.4" in bp                     # accounted for as optional (owner decision)
    ci_text = open(CI_YML, encoding="utf-8").read()
    assert "rustup" not in ci_text and "maturin" not in ci_text and "cargo" not in ci_text   # normal CI needs no Rust


def test_doc_cites_owner_decision():
    with open(OD_JSON, "rb") as fh:
        assert hashlib.sha256(fh.read()).hexdigest() == OD_JSON_SHA256
    od = open(OD_JSON, encoding="utf-8").read()
    assert "OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES" in od and "PYTHON_CANONICAL_FOR_FROZEN_AND_SCORE_BEARING" in od
    doc = open(DOC, encoding="utf-8").read()
    for s in (OD_JSON_SHA256, "S10.4", "RUST-OQ-02", "S10.3", "OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES",
              "PYTHON_CANONICAL_FOR_FROZEN_AND_SCORE_BEARING", "parity_prereg_v1.json"):
        assert s in doc, s
    _, text = _load(WF)
    assert "S10.4" in text and "OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES" in text


# ------------------------------------------------------------------------------- CLI entry points (no Rust needed)
def test_source_status_entry_point(tmp_path, capsys):
    V = _verify()
    out = tmp_path / "gh_output"
    assert V.main(["--source-status", "--github-output", str(out)]) == 0
    st = json.loads(capsys.readouterr().out)
    lines = dict(ln.split("=", 1) for ln in out.read_text().splitlines())
    assert set(lines) == set(V.SOURCE_STATUS_KEYS)
    for k in V.SOURCE_STATUS_KEYS:
        assert lines[k] == ("true" if st[k] else "false")
    rep = json.load(open(REPORT))
    current = {s: V.sha256_file(s) for s in V.PROVENANCE_SOURCES}
    assert st["sources_match_recorded_build"] == (current == rep["build_provenance"]["source_sha256"])
    assert st["recorded_verdicts"] == rep["verdicts"]


def test_cli_flag_combinations_refused():
    V = _verify()
    with pytest.raises(SystemExit):
        V.main(["--strict"])                                  # --strict only with --dev
    with pytest.raises(SystemExit):
        V.main(["--github-output", "x"])                      # only with --source-status


def test_dev_strict_refuses_partial_runs(monkeypatch, capsys):
    V = _verify()
    monkeypatch.setattr(V.TB, "rust_available", lambda: True)
    assert V.dev(["K4_trace"], None, strict=True) == 2
    assert V.dev(None, 3, strict=True) == 2
    assert "not allowed" in capsys.readouterr().out


def test_dev_strict_without_extension_is_an_error():
    V = _verify()
    if V.TB.rust_available():                                 # a built extension in this env: refusal path not reachable
        assert V.TB.rust_unavailable_reason() is None
        return
    assert V.main(["--dev", "--strict"]) == 2
