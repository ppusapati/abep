"""Optional Rust CI for abep_core (.github/workflows/rust-parity.yml; docs/ci/RUST_PARITY.md).

Owner decision A9.14 S10.4 (RUST-OQ-02, OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES;
docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md, json sha256 c6c00b7f...). Structural checks of the workflow
(triggers, steps, conditions, pins, no secrets, not a required context), a walk of the step conditions for the events
that matter (fail-closed on an unrecorded Rust change; the v2 scoring seed spent only on an explicit dispatch; no v2 rerun
after a recorded failure; upload only of a report the campaign wrote), plus the non-interactive CLI entry points of
scripts/verify_abep_core.py exercised without a Rust toolchain, and a real-extension smoke when abep_core is importable.
Never skips (CLAUDE.md rule 9). No campaign is run.

Registration in force: parity v2 (parity_prereg_v2.json / parity_report_v2.json, the records verify_abep_core.py and
tpmc_backend.py read since A9.14 S10.4). The v1 records are immutable history; this file only checks that the workflow no
longer reads them.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re

import numpy as np
import pytest
import yaml  # PyYAML is locked (requirements-lock.txt); imported directly so a missing dep fails, never adds a skip.

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows", "rust-parity.yml")
CI_YML = os.path.join(ROOT, ".github", "workflows", "ci.yml")
REPORT = os.path.join(ROOT, "docs", "performance", "abep_core", "parity_report_v2.json")
PREREG = os.path.join(ROOT, "docs", "performance", "abep_core", "parity_prereg_v2.json")
V1_RECORDS = ("parity_prereg_v1.json", "parity_report_v1.json", "parity_report_v1.md")   # immutable history, never read
DOC = os.path.join(ROOT, "docs", "ci", "RUST_PARITY.md")
OD_JSON = os.path.join(ROOT, "docs", "decisions", "OD_2026_10_01_A9_14_s7_s10_owner_decisions.json")
OD_JSON_SHA256 = "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c"

WATCHED_PATHS = {"abep_core/**", "abep_sim/design/tpmc_backend.py", "abep_sim/intake_tpmc.py",
                 "scripts/verify_abep_core.py", "docs/performance/abep_core/**", ".github/workflows/rust-parity.yml"}
ALLOWED_ACTIONS = {"actions/checkout@v4", "actions/setup-python@v5", "actions/upload-artifact@v4"}
CHANGED = "steps.src.outputs.sources_match_recorded_build != 'true'"
UNCHANGED = "steps.src.outputs.sources_match_recorded_build == 'true'"
SCORING = "(github.event_name == 'workflow_dispatch' && inputs.run_scoring_campaign)"


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
    assert set(on["workflow_dispatch"]["inputs"]) == {"run_scoring_campaign"}


def test_watched_paths_cover_every_provenance_source():
    V = _verify()
    for src in V.PROVENANCE_SOURCES:
        assert src in WATCHED_PATHS or (src.startswith("abep_core/") and "abep_core/**" in WATCHED_PATHS), src


def test_workflow_reads_the_registration_in_force():
    """The workflow reads the records verify_abep_core.py / tpmc_backend.py read (v2), never the v1 history."""
    V = _verify()
    assert V.PREREG_REL.endswith("/parity_prereg_v2.json") and V.REPORT_REL.endswith("/parity_report_v2.json")
    _, text = _load(WF)
    code = "\n".join(s.get("run", "") for s in _steps())          # every executed step, not the header comments
    assert V.REPORT_REL in code and V.MD_REL in code
    assert "parity_prereg_v2" in code and "parity_prereg_v3" in code   # reference refusal names the next registration
    for old in V1_RECORDS + ("parity_prereg_v1", "parity_report_v1", "REFUSED_V1_", "rust-parity-v1-"):
        assert old not in code, old
    assert "rust-parity-v1-" not in text and "REFUSED_V1_" not in text
    # the v1 records stay unchanged history: their bytes equal the hashes v2 records in `supersedes`
    sup = json.load(open(PREREG))["supersedes"]
    for rel, sha in ((sup["path"], sup["sha256"]), (sup["v1_report"]["path"], sup["v1_report"]["sha256"]),
                     (sup["v1_report"]["md"], sup["v1_report"]["md_sha256"])):
        assert os.path.basename(rel) in V1_RECORDS
        with open(os.path.join(ROOT, rel), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == sha, rel


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
def _eval_if(expr, event, scoring_input, outputs):
    """Evaluate the workflow's `if:` expressions for one simulated event (only the operators the workflow uses)."""
    py = re.sub(r"steps\.(\w+)\.outputs\.(\w+)", lambda m: repr(outputs.get(m.group(1), {}).get(m.group(2), "")), expr)
    py = py.replace("github.event_name", repr(event))
    py = py.replace("inputs.run_scoring_campaign", repr(bool(scoring_input) and event == "workflow_dispatch"))
    py = py.replace("always()", "True").replace("&&", " and ").replace("||", " or ")
    py = re.sub(r"!(?!=)", " not ", py)
    assert re.fullmatch(r"[\w\s'()=!.\-]+", py), py
    return bool(eval(py, {"__builtins__": {}}, {}))


def _simulate(event, scoring_input, src, ext, campaign_wrote):
    """Steps that run, in order, and whether the job ends green. Only the unconditional error steps ('Refuse ...',
    'Unrecorded source change ...') are modelled as failing; a failure skips every later step without always()."""
    outputs = {"src": src, "ext": ext}           # step outputs exist only once their step ran
    ran, ok = [], True
    for st in _steps():
        name = st.get("name", st.get("uses"))
        expr = st.get("if")
        if not ok and (expr is None or "always()" not in expr):
            continue
        if expr is not None and not _eval_if(expr, event, scoring_input, outputs):
            continue
        ran.append(name)
        if st.get("id") == "campaign":
            outputs["campaign"] = {"report_written": "true" if campaign_wrote else "false"}
        if "exit 1" in st.get("run", "") and (name.startswith("Refuse") or name.startswith("Unrecorded")):
            ok = False
    return ran, ok


def _src(match, failure=False, rerun=False):
    return {"sources_match_recorded_build": "true" if match else "false", "reference_matches_prereg": "true",
            "v1_scoring_failure_on_record": "true" if failure else "false",
            "v1_rerun_after_failure_on_record": "true" if rerun else "false", "campaign_history_length": "2"}


def test_step_order_and_conditions():
    names = [s.get("name", s.get("uses")) for s in _steps()]
    order = ["Sources vs the recorded build", "Refuse a changed Python reference", "Refuse a committed v2 rerun",
             "Parity record check", "Refuse a scoring request with nothing to score", "Refuse a v2 scoring rerun",
             "Install the pinned Rust toolchain", "Pure-Rust unit tests", "Build abep_core", "Extension state",
             "Extension-dependent pytest - recorded binary", "Extension-dependent pytest - CI binary",
             "Parity suite", "Bitwise reproduction", "Unrecorded source change - fail closed",
             "FULL pre-registered parity campaign", "Upload the campaign report", "Campaign re-admits every kernel"]
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


def test_extension_dependent_pytest_runs_with_the_built_extension():
    """RUSTCI-3: the repository's real-extension pytest branches run with the CI-built abep_core."""
    full = _step("Extension-dependent pytest - recorded binary")
    assert full["if"] == UNCHANGED + " && steps.ext.outputs.extension_is_recorded_build == 'true'"
    assert full["run"] == ('"$RUNNER_TEMP/venv_rust/bin/python" -m pytest -q tests/test_tpmc_backend.py '
                           "tests/test_rust_ci_workflow.py")
    part = _step("Extension-dependent pytest - CI binary")
    assert part["if"] == CHANGED + " || steps.ext.outputs.extension_is_recorded_build != 'true'"
    assert ('"$RUNNER_TEMP/venv_rust/bin/python" -m pytest -q tests/test_tpmc_backend.py tests/test_rust_ci_workflow.py'
            in part["run"])
    # only the two record-bound tests are deselected; their real-extension assertions run here on the CI binary
    assert sorted(re.findall(r"--deselect (\S+)", part["run"])) == [
        "tests/test_tpmc_backend.py::test_report_rederives_and_is_consistent",
        "tests/test_tpmc_backend.py::test_rust_state_real"]
    assert "test_real_extension_smoke_unadmitted_context" in part["run"]
    assert callable(globals()["test_real_extension_smoke_unadmitted_context"])


def test_scoring_campaign_only_on_explicit_dispatch_and_must_readmit():
    """RUSTCI-1: push / pull_request never spend the v2 scoring seed; they fail closed on an unrecorded change."""
    doc, _ = _load(WF)
    inp = doc["on"]["workflow_dispatch"]["inputs"]["run_scoring_campaign"]
    assert inp["type"] == "boolean" and inp["default"] is False
    camp = _step("FULL pre-registered parity campaign")
    assert camp["id"] == "campaign" and camp["if"] == CHANGED + " && " + SCORING
    assert '"$RUNNER_TEMP/venv_rust/bin/python" scripts/verify_abep_core.py\n' in camp["run"]   # scoring: no flags
    assert camp["env"]["HISTORY_BEFORE"] == "${{ steps.src.outputs.campaign_history_length }}"
    closed = _step("Unrecorded source change - fail closed")
    assert closed["if"] == CHANGED + " && !" + SCORING
    assert "UNRECORDED_SOURCE_CHANGE" in closed["run"] and "exit 1" in closed["run"]
    gate = _step("Campaign re-admits every kernel")
    assert gate["if"] == CHANGED + " && " + SCORING
    assert "--check" in gate["run"] and 'x == "ADMITTED"' in gate["run"] and "sys.exit(" in gate["run"]
    for name in ("Refuse a scoring request with nothing to score", "Refuse a v2 scoring rerun"):
        assert _step(name)["if"].startswith(SCORING + " && ") and "exit 1" in _step(name)["run"]
    assert _step("Refuse a scoring request with nothing to score")["if"].endswith(UNCHANGED)
    assert _step("Refuse a v2 scoring rerun")["if"].endswith("steps.src.outputs.v1_scoring_failure_on_record == 'true'")
    assert _step("Refuse a committed v2 rerun")["if"] == "steps.src.outputs.v1_rerun_after_failure_on_record == 'true'"


def test_simulated_events():
    """RUSTCI-1 / RUSTCI-4: walk the step conditions for the events that matter."""
    camp, closed, up = "FULL pre-registered parity campaign", "Unrecorded source change - fail closed", "Upload the campaign"
    has = lambda ran, part: any(part in n for n in ran)                                         # noqa: E731
    ext = {"extension_is_recorded_build": "false"}
    for event in ("push", "pull_request", "workflow_dispatch"):          # changed sources, no scoring request
        ran, ok = _simulate(event, False, _src(False), ext, False)
        assert not has(ran, camp) and has(ran, closed) and not ok, (event, ran)
        assert has(ran, "Parity suite") and has(ran, "Extension-dependent pytest - CI binary")  # smoke before failing
    for event in ("push", "pull_request"):                               # a scoring input outside dispatch is ignored
        ran, ok = _simulate(event, True, _src(False), ext, True)
        assert not has(ran, camp) and not has(ran, up) and not ok
    ran, ok = _simulate("workflow_dispatch", True, _src(False), ext, True)
    assert has(ran, camp) and has(ran, up) and has(ran, "Campaign re-admits") and not has(ran, closed) and ok
    ran, _ = _simulate("workflow_dispatch", True, _src(False), ext, False)   # refused / crashed before write_report
    assert has(ran, camp) and not has(ran, up)
    ran, ok = _simulate("workflow_dispatch", True, _src(False, failure=True), ext, True)
    assert not has(ran, camp) and not has(ran, up) and not ok          # no v2 rerun after a recorded failure
    ran, ok = _simulate("workflow_dispatch", True, _src(True), ext, True)
    assert not has(ran, camp) and not ok                                # nothing to score: the seed is not spent
    ran, ok = _simulate("push", False, _src(True, failure=True, rerun=True), ext, False)
    assert not ok and not has(ran, camp)                                # a committed v2 rerun after a failure fails
    for event in ("push", "pull_request", "workflow_dispatch"):          # recorded sources: green path, no campaign
        ran, ok = _simulate(event, False, _src(True), ext, False)
        assert ok and not has(ran, camp) and has(ran, "Parity record check") and has(ran, "Note when the CI binary")
    ran, ok = _simulate("push", False, _src(True), {"extension_is_recorded_build": "true"}, False)
    assert ok and has(ran, "Extension-dependent pytest - recorded binary") and has(ran, "Bitwise reproduction")
    assert not has(ran, "Extension-dependent pytest - CI binary")


def test_concurrency_serialises_scoring_globally():
    doc, _ = _load(WF)
    grp = doc["concurrency"]["group"]
    assert SCORING in grp and "'rust-parity-v2-scoring'" in grp and "github.ref" in grp
    assert doc["concurrency"]["cancel-in-progress"] is False


def test_upload_only_when_the_campaign_wrote_its_report():
    """RUSTCI-4: never upload the unchanged committed report as if it were a CI execution's report."""
    up = _step("Upload the campaign report")
    assert up["uses"] == "actions/upload-artifact@v4"
    assert up["if"] == "always() && steps.campaign.outputs.report_written == 'true'"
    assert up["with"]["path"] == "${{ runner.temp }}/parity_campaign_record/"
    assert up["with"]["if-no-files-found"] == "error"
    run = _step("FULL pre-registered parity campaign")["run"]
    assert "set +e" in run and "rc=$?" in run and run.rstrip().endswith("exit $rc")
    assert '"$after" -gt "$HISTORY_BEFORE"' in run and "report_written=true" in run and "report_written=false" in run
    assert '"$RUNNER_TEMP/parity_campaign_record/"' in run and "GITHUB_STEP_SUMMARY" in run


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
              "PYTHON_CANONICAL_FOR_FROZEN_AND_SCORE_BEARING", "parity_prereg_v2.json", "parity_report_v2.json",
              "UNRECORDED_SOURCE_CHANGE", "REFUSED_V2_RERUN_AFTER_FAILURE", "rust-parity-v2-scoring", "run_scoring_campaign"):
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
    assert set(lines) == set(V.SOURCE_STATUS_KEYS) | {"campaign_history_length"}
    for k in V.SOURCE_STATUS_KEYS:
        assert lines[k] == ("true" if st[k] else "false")
    # compare with the record the CLI reads (V.REPORT_REL; parity registration v2 since A9.14 S10.4), not the v1 record
    assert os.path.join(ROOT, V.REPORT_REL) == REPORT and os.path.join(ROOT, V.PREREG_REL) == PREREG
    rep = json.load(open(os.path.join(ROOT, V.REPORT_REL)))
    assert lines["campaign_history_length"] == str(len(rep["campaign_history"])) == str(st["campaign_history_length"])
    current = {s: V.sha256_file(s) for s in V.PROVENANCE_SOURCES}
    assert st["sources_match_recorded_build"] == (current == rep["build_provenance"]["source_sha256"])
    assert st["recorded_verdicts"] == rep["verdicts"]
    # the committed v2 record holds only ADMITTED v2 executions (flags keep their v1_* key names; evaluated against v2)
    assert st["v1_scoring_failure_on_record"] is False and st["v1_rerun_after_failure_on_record"] is False


def test_scoring_history_flags():
    """RUSTCI-1: the v2 record is read against v2 decision_rules.no_retuning (a failure; a v2 rerun after one)."""
    V = _verify()
    pre = json.load(open(PREREG))
    sha = V.sha256_file(V.PREREG_REL)
    seed = pre["campaign_seeds"]["scoring_master_seed"]
    ok = {"master_seed": seed, "prereg_sha256": sha, "verdicts": {"K1_entry": "ADMITTED", "K4_trace": "ADMITTED"}}
    bad = {"master_seed": seed, "prereg_sha256": sha, "verdicts": {"K1_entry": "ADMITTED", "K4_trace": "NOT_ADMITTED"}}
    other_seed = dict(bad, master_seed=seed + 1)
    other_prereg = dict(bad, prereg_sha256="0" * 64)
    assert V.scoring_history_flags([], pre, sha) == (False, False)
    assert V.scoring_history_flags([ok, ok], pre, sha) == (False, False)
    assert V.scoring_history_flags([ok, bad], pre, sha) == (True, False)
    assert V.scoring_history_flags([bad, ok], pre, sha) == (True, True)
    assert V.scoring_history_flags([bad, bad], pre, sha) == (True, True)
    assert V.scoring_history_flags([dict(ok, verdicts={})], pre, sha) == (True, False)   # no verdict is not ADMITTED
    assert V.scoring_history_flags([other_seed, ok], pre, sha) == (False, False)          # not a v2 scoring execution
    assert V.scoring_history_flags([other_prereg, ok], pre, sha) == (False, False)
    rep = json.load(open(REPORT))
    assert V.scoring_history_flags(rep["campaign_history"], pre, sha) == (False, False)


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


# ------------------------------------------------------------------------- real extension (CI venv; RUSTCI-3)
def test_real_extension_smoke_unadmitted_context():
    """With the CI-built abep_core (any build, admitted or not), the assertions of test_tpmc_backend.test_rust_state_real
    run inside parity_campaign_unadmitted() - the only context in which an unadmitted build may run. Outside it the
    admission gate still decides. Without the extension, a rust request raises (no skip, no fallback)."""
    from abep_sim import intake_tpmc as REF
    from abep_sim.atmosphere import atmosphere
    from abep_sim.constants import K_B, M_SPECIES
    from abep_sim.design import tpmc_backend as TB

    atm = atmosphere(200.0, "mean")
    m, r = M_SPECIES["N2"], 5e-3
    if not TB.rust_available():
        with pytest.raises(TB.RustBackendUnavailable, match="abep_core"):
            TB.trace_channel(np.random.default_rng(0), np.ones((2, 3)), r, 0.05, 0.5, 350.0, m, backend="rust")
        return
    import abep_core
    assert abep_core.K_B == K_B
    ok, _why = TB.admission_status(abep_core, "K4_trace")
    v0 = REF._flux_weighted_entry(np.random.default_rng(7), 3000, atm["V"], math.radians(2.0), atm["T"], m)
    if not ok:                                                 # an unadmitted build is refused outside the campaign
        with pytest.raises(TB.RustBackendNotAdmitted, match="NOT_ADMITTED_BUILD"):
            TB.trace_channel(np.random.default_rng(8), v0, r, 0.1, 0.7, 350.0, m, backend="rust")
    with TB.parity_campaign_unadmitted():
        a = TB.trace_channel(np.random.default_rng(8), v0, r, 0.1, 0.7, 350.0, m, backend="rust")
        b = TB.trace_channel(np.random.default_rng(8), v0, r, 0.1, 0.7, 350.0, m, backend="rust")
        with pytest.raises(ValueError):
            TB.trace_channel(np.random.default_rng(0), v0, r, 0.1, 0.7, 350.0, m, max_hits=0, backend="rust")
        with pytest.raises(ValueError):
            TB.trace_channel(np.random.default_rng(0), v0, r, 0.1, 0.7, 350.0, m, scattering="Maxwell", backend="rust")
    py = TB.trace_channel(np.random.default_rng(9), v0, r, 0.1, 0.7, 350.0, m)
    for x, y in zip(a, b):                                     # deterministic seeding
        if isinstance(x, np.ndarray):
            assert x.dtype == y.dtype and x.shape == y.shape and np.array_equal(x, y)
        else:
            assert x == y
    col, v, hits, back, unres = a
    assert col.dtype == np.bool_ and back.dtype == np.bool_ and v.shape == (3000, 3) and hits.dtype.kind == "i"
    assert isinstance(unres, float) and not np.any(col & back)
    n = len(v0)
    for x, y in ((a[0], py[0]), (a[3], py[3])):               # z = 5, as pre-registered
        p1, p2 = x.mean(), y.mean()
        se = math.sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n)
        assert abs(p1 - p2) <= 5.0 * se + 1e-15
    h1, h2 = a[2].astype(float), py[2].astype(float)
    assert abs(h1.mean() - h2.mean()) <= 5.0 * math.sqrt(h1.var(ddof=1) / n + h2.var(ddof=1) / n)


def test_real_extension_smoke_with_a_non_recorded_binary(monkeypatch):
    """The CI-binary case: the same smoke when the importable extension is NOT the recorded build (sha256 forced)."""
    from abep_sim.design import tpmc_backend as TB
    TB.clear_admission_cache()
    monkeypatch.setattr(TB, "extension_sha256", lambda mod: "0" * 64)
    try:
        if TB.rust_available():
            import abep_core
            assert not TB.admission_status(abep_core, "K4_trace")[0]
        test_real_extension_smoke_unadmitted_context()
    finally:
        monkeypatch.undo()
        TB.clear_admission_cache()
