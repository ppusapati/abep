"""Repository-integrity checks (scripts/ci_checks.py, docs/ci/CI.md): they pass on the committed tree, they write nothing, and
they detect tampering. Every tamper test works on a copy in tmp_path; the repository itself is never modified. Fast (seconds).
No test here is skipped or xfailed (CLAUDE.md rule 9 counts stay 5 skipped / 1 xfail)."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("ci_checks", os.path.join(ROOT, "scripts", "ci_checks.py"))
ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci)


def _copy_tree(src, dst):
    """Copy repository content (src = the root or a directory below it) without .git, run output, caches or environments."""
    def ignore(d, names):
        rel = os.path.relpath(d, ROOT)                  # prune paths are relative to the repository root
        return {n for n in names if n in ci.PRUNE_NAMES or n.endswith(".egg-info")
                or os.path.normpath(os.path.join(rel, n)) in ci.PRUNE_RELPATHS}
    shutil.copytree(src, dst, ignore=ignore)
    return str(dst)


def _append(path, text):
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)


def test_all_checks_pass_on_committed_tree():
    res = ci.run_checks()
    assert set(res) == set(ci.CHECKS)
    failing = {k: p for k, (p, _) in res.items() if p}
    assert not failing, failing


def test_generators_run_in_memory_and_write_nothing():
    targets = [os.path.join(ci.BR, "cases", "p5_n2.json"), os.path.join(ci.PROP, "n2_n_di_lower.toml")]
    before = {p: os.stat(p).st_mtime_ns for p in targets}
    cases = ci.run_generator("make_p5_n2_cases.py")
    variants = ci.run_generator("make_n2_variant_configs.py")
    assert {p: os.stat(p).st_mtime_ns for p in targets} == before
    with open(targets[0], "rb") as f:
        assert cases[targets[0]] == f.read()
    with open(targets[1], "rb") as f:
        assert variants[targets[1]] == f.read()


def test_write_capture_captures_and_refuses(tmp_path):
    import builtins, io
    real_open = builtins.open
    keep = tmp_path / "keep.txt"
    keep.write_text("unchanged\n")
    with ci.WriteCapture() as cap:
        with open(tmp_path / "a.txt", "w") as f:
            f.write("x\n")
        json.dump({"k": 1}, open(tmp_path / "b.json", "w"), indent=1)       # never closed, as the generators do
        (tmp_path / "c.bin").write_bytes(b"\x00\x01")                        # pathlib goes through io.open
        os.makedirs(tmp_path / "newdir", exist_ok=True)
        assert open(keep).read() == "unchanged\n"                            # reads pass through
        for bad in (lambda: open(keep, "a"), lambda: open(keep, "r+"), lambda: os.remove(keep),
                    lambda: os.replace(keep, tmp_path / "moved.txt"), lambda: shutil.rmtree(tmp_path)):
            with pytest.raises(RuntimeError):
                bad()
    assert builtins.open is real_open and io.open is real_open
    assert sorted(os.listdir(tmp_path)) == ["keep.txt"] and keep.read_text() == "unchanged\n"
    assert cap.files == {str(tmp_path / "a.txt"): b"x\n", str(tmp_path / "b.json"): b'{\n "k": 1\n}',
                         str(tmp_path / "c.bin"): b"\x00\x01"}


def test_compare_with_committed_detects_drift(tmp_path):
    f = tmp_path / "x.json"
    f.write_text('{"a": 1}')
    assert ci.compare_with_committed({str(f): b'{"a": 1}'}, "t") == []
    assert "formatting only" in ci.compare_with_committed({str(f): b'{\n "a": 1\n}'}, "t")[0]
    assert "content differs" in ci.compare_with_committed({str(f): b'{"a": 2}'}, "t")[0]
    assert "not committed" in ci.compare_with_committed({str(tmp_path / "new.json"): b"{}"}, "t")[0]
    assert "no output" in ci.compare_with_committed({}, "t")[0]


def test_parse_tree_reports_bad_files_and_prunes_run_output(tmp_path):
    (tmp_path / "good.json").write_text('{"a": [1, 2]}')
    (tmp_path / "dup.json").write_text('{"a": 1, "a": 2}')
    (tmp_path / "bad.toml").write_text("a = = 1\n")
    (tmp_path / "ok.toml").write_text('a = "b"\n')
    for pruned in ("hallthruster_bridge/out", ".venv/lib", "__pycache__", ".claude/worktrees/x", "results"):
        (tmp_path / pruned).mkdir(parents=True)
        (tmp_path / pruned / "broken.json").write_text("{")
    bad, n = ci.parse_tree(str(tmp_path))
    assert n == {".json": 1, ".toml": 1}
    assert len(bad) == 2 and any("duplicate JSON key" in b for b in bad) and any(b.startswith("bad.toml") for b in bad)


def test_pin_checks_detect_tampering(tmp_path):
    br = _copy_tree(ci.BR, tmp_path / "bridge")
    for check in (ci.check_prereg_lock, ci.check_audit_manifest, ci.check_hallthruster_pin):
        assert check(br)[0] == [], check.__name__
    assert ci.check_rate_validity_coverage(os.path.join(br, "propellants"))[0] == []

    _append(os.path.join(br, "cases", "p5_n2.json"), " ")                   # locked AND pinned by the criteria
    bad = ci.check_prereg_lock(br)[0]
    assert any(b.startswith("prereg lock: cases/p5_n2.json") for b in bad)
    assert any(b.startswith("criteria inputs_pinned.cases") for b in bad)

    _append(os.path.join(br, "propellants", "n2_n_rot_off.toml"), "\n# edited\n")   # pinned chemistry config
    assert any("n2_n_rot_off.toml" in b for b in ci.check_prereg_lock(br)[0])

    _append(os.path.join(br, "propellants", "dissociation_N2.dat"), "0.0\t0.0\n")    # rate table pinned by the audit MANIFEST
    assert any("dissociation_N2.dat" in b for b in ci.check_audit_manifest(br)[0])

    _append(os.path.join(br, "audit", "configs", "p5_n2_cases_blind_envelope_v1.json"), " ")
    assert any("p5_n2_cases_blind_envelope_v1.json" in b for b in ci.check_audit_manifest(br)[0])

    man = os.path.join(br, "Manifest.toml")
    with open(man, encoding="utf-8") as f:
        txt = f.read()
    with open(man, "w", encoding="utf-8") as f:
        f.write(txt.replace("bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5", "0" * 40))
    assert any("repo-rev" in b for b in ci.check_hallthruster_pin(br)[0])

    with open(os.path.join(br, "propellants", "zz_new.toml"), "w", encoding="utf-8") as f:
        f.write('[[reactions]]\ntype = "excitation"\ntarget_species = "N2"\nrate_coeff_file = "no_such_table.dat"\n')
    bad = ci.check_rate_validity_coverage(os.path.join(br, "propellants"))[0]
    assert any("no_such_table.dat is missing" in b for b in bad) and any("no rate_validity.toml entry" in b for b in bad)


def test_cli_detects_generated_artefact_drift_on_a_copy(tmp_path):
    repo = _copy_tree(ROOT, tmp_path / "repo")
    script = os.path.join(repo, "scripts", "ci_checks.py")
    run = lambda *a: subprocess.run([sys.executable, script, *a], capture_output=True, text=True, timeout=120)
    ok = run("--only", "variant_configs,p5_n2_cases,launch_manifests")
    assert ok.returncode == 0, ok.stdout + ok.stderr

    _append(os.path.join(repo, "hallthruster_bridge", "propellants", "n2_n_nel_wang.toml"), "\n# hand edit\n")
    cases = os.path.join(repo, "hallthruster_bridge", "cases", "p5_n2.json")
    with open(cases, encoding="utf-8") as f:
        d = json.load(f)
    with open(cases, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)                                            # same content, different bytes
    mdir = os.path.join(repo, "hallthruster_bridge", "campaign", "manifests")
    shutil.copy(os.path.join(mdir, "staged_n2_n_rot_off.json"), os.path.join(mdir, "staged_orphan.json"))
    r = run("--only", "variant_configs,p5_n2_cases,launch_manifests")
    assert r.returncode == 1
    assert "n2_n_nel_wang.toml differs from a fresh generation" in r.stdout
    assert "p5_n2.json differs from a fresh generation (parsed content equal: formatting only)" in r.stdout
    assert "staged_orphan.json is committed but not produced by build()" in r.stdout
    assert "ci_checks: 0/3 passed" in r.stdout


def _junit(tmp_path, cases):
    xml = ['<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">']
    for name, child in cases:
        xml.append(f'<testcase classname="tests.test_sim" name="{name}">{child}</testcase>')
    xml.append("</testsuite></testsuites>")
    p = tmp_path / "r.xml"
    p.write_text("".join(xml))
    return str(p)


def test_pytest_outcome_rule(tmp_path):
    skip = '<skipped type="pytest.skip" message="SUPERSEDED: 0-D Hall closure ..."/>'
    xfail = '<skipped type="pytest.xfail" message="Gate 3: ..."/>'
    good = [(f"test_s{i}", skip) for i in range(5)] + [("test_v16_blind_validation_p5_nitrogen", xfail), ("test_ok", "")]
    assert ci.check_pytest_outcomes(_junit(tmp_path, good))[0] == []
    assert ci.check_pytest_outcomes(_junit(tmp_path, good + [("test_new", skip)]))[0]                   # 6 skips
    other = '<skipped type="pytest.skip" message="pymsis missing"/>'
    assert ci.check_pytest_outcomes(_junit(tmp_path, good[1:] + [("test_x", other)]))[0]               # not SUPERSEDED
    assert ci.check_pytest_outcomes(_junit(tmp_path, good[:5] + [("test_ok", "")]))[0]                 # xfail missing
    fail = '<failure message="boom"/>'
    assert ci.check_pytest_outcomes(_junit(tmp_path, good + [("test_f", fail)]))[0]
    assert ci.check_pytest_outcomes(_junit(tmp_path, []))[0]                                           # empty report


def test_cli_usage():
    assert ci.main(["--list"]) == 0
    assert ci.main(["--only", "no_such_check"]) == 2
    assert ci.main(["--pytest-junit"]) == 2


def _workflow(name):
    import yaml
    with open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8") as f:
        text = f.read()
    doc = yaml.safe_load(text)
    return doc, doc.get("on", doc.get(True)), text                          # YAML 1.1 reads a bare `on` key as True


def test_ci_workflow_runs_the_gates():
    doc, on, text = _workflow("ci.yml")
    assert set(on) == {"pull_request", "push"} and on["push"]["branches"] == ["main"]
    runs = "\n".join(s.get("run", "") for j in doc["jobs"].values() for s in j["steps"])
    for cmd in ("python -m pytest -q tests", "python -m abep_sim.golden check", "python scripts/ci_checks.py",
                "python scripts/ci_checks.py --pytest-junit"):
        assert cmd in runs, cmd
    assert "julia" not in runs.lower()                                       # no Hall-thruster run on push or pull request
    assert doc["jobs"]["tests"]["strategy"]["matrix"]["pymsis"] == ["present", "absent"]


def test_julia_smoke_is_manual_construction_only():
    doc, on, text = _workflow("julia-smoke.yml")
    assert set(on) == {"workflow_dispatch"}
    steps = doc["jobs"]["smoke"]["steps"]
    assert "upload-artifact" not in text and "hallthruster_bridge/out" not in text
    smoke = [s for s in steps if "p5_n2_campaign.jl" in s.get("run", "")]
    assert len(smoke) == 1 and smoke[0]["env"]["P5N2_SMOKE"] == "1"
    assert '"$RUNNER_TEMP/p5n2_smoke/smoke.jsonl" vacuum 0 "$NJOBS" n2_n.toml' in smoke[0]["run"]
    assert any("Pkg.instantiate()" in s.get("run", "") and "check_pin()" in s.get("run", "") for s in steps)
    assert steps[-1].get("if") == "always()" and 'rm -rf "$RUNNER_TEMP/p5n2_smoke"' in steps[-1]["run"]
