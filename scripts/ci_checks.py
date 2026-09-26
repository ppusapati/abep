"""Static repository-integrity checks for CI (docs/ci/CI.md). Fast (seconds), no Julia, no simulation, writes NO file.

Each check returns (problems, note): an empty problem list is a pass, the note says what was verified. The checks enforce the
evidence chain of CLAUDE.md / docs/EVIDENCE.md mechanically. They never change physics, thresholds, frozen data or chemistry,
and they never read campaign records (hallthruster_bridge/out/ and any run output are out of scope).

  parse_json_toml          every *.json and *.toml in the repository parses (a duplicate JSON key is an error)
  prereg_lock              hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json: every listed file matches its sha256; the
                           inputs pinned by the P5-N2 criteria (measurement audit, case set, transport candidates, chemistry
                           configs) match theirs (the same refusal conditions the campaign driver applies at start-up)
  audit_manifest           hallthruster_bridge/audit/configs/MANIFEST.json: snapshot sha256, rate-file set and rate-table
                           sha256 of every immutable audit configuration, and the case-file snapshots
  hallthruster_pin         PINNED.toml commit / version / repository == the Manifest.toml HallThruster entry; Project.toml compat
  rate_validity_coverage   every rate file named by a propellant config exists and has a rate_validity.toml entry
  variant_configs          scripts/make_n2_variant_configs.py VARIANTS == committed propellant TOMLs (byte for byte; no orphan)
  p5_n2_cases              scripts/make_p5_n2_cases.py == hallthruster_bridge/cases/p5_n2.json (byte for byte)
  launch_manifests         scripts/make_p5_n2_launch_manifests.py build() == campaign/manifests/*.json (byte for byte; no orphan)
  multiply_charged_tables  scripts/build_multiply_charged_tables.py == committed .dat and .dat.source (byte for byte; this is
                           the comparison its --check mode makes, plus the .source provenance files, without a temp directory)
  ensemble_gate            abep_sim.hall_ensemble.load_ensemble() loads; require_admitted refuses every screening candidate

"Fresh generation" runs each generator's OWN write path (its __main__, default arguments) inside WriteCapture: builtins.open /
io.open in a writing mode return in-memory buffers, directory creation is a no-op, every move / remove / copy call raises and
no bytecode is cached, so nothing reaches the disk. The captured bytes are compared with the committed files.

Separate mode, used by CI after pytest (CLAUDE.md rule 9: all pass, 5 skipped = the SUPERSEDED 0-D Hall calibration, 1 strict
xfail = test_v16_blind_validation_p5_nitrogen):
  python scripts/ci_checks.py --pytest-junit report.xml

Usage: python scripts/ci_checks.py [--list] [--only NAME[,NAME...]] [--pytest-junit PATH]      exit 0 pass, 1 fail, 2 usage
"""
from __future__ import annotations

import builtins, contextlib, hashlib, importlib.util, io, json, locale, os, runpy, shutil, sys, time, tomllib
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
BR = os.path.join(ROOT, "hallthruster_bridge")
PROP = os.path.join(BR, "propellants")
SCRIPTS = os.path.join(ROOT, "scripts")

# parse_json_toml: pruned directories. ".git" and "hallthruster_bridge/out" (raw run output, gitignored) as specified; the
# others are gitignored run output ("results") or local environments / tool caches / agent worktrees, not repository content.
PRUNE_RELPATHS = {".git", os.path.join("hallthruster_bridge", "out"), "results"}
PRUNE_NAMES = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", ".claude"}

# CLAUDE.md rule 9 (expected pytest outcome). Change only together with an owner-logged change of that rule.
EXPECTED_SKIPPED = 5
EXPECTED_SKIP_REASON_PREFIX = "SUPERSEDED"
EXPECTED_XFAIL = frozenset({"test_v16_blind_validation_p5_nitrogen"})


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


def _json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _toml(path: str) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def verify_sha_map(base_dir: str, pins: dict, label: str) -> list[str]:
    """Every {path relative to base_dir: sha256} entry exists and matches."""
    bad = []
    for rel, want in pins.items():
        p = os.path.join(base_dir, rel)
        if not os.path.isfile(p):
            bad.append(f"{label}: {rel} is missing")
        elif (got := sha256_file(p)) != want:
            bad.append(f"{label}: {rel} sha256 {got[:16]}... != pinned {str(want)[:16]}...")
    return bad


# ---------------------------------------------------------------------------------------------------------------- parsing
def _no_duplicate_keys(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError(f"duplicate JSON key {k!r}")
        seen[k] = v
    return seen


def iter_data_files(root: str = ROOT, suffixes=(".json", ".toml")):
    for d, dirs, files in os.walk(root):
        rel_d = os.path.relpath(d, root)
        dirs[:] = sorted(x for x in dirs if x not in PRUNE_NAMES and not x.endswith(".egg-info")
                         and os.path.normpath(os.path.join(rel_d, x)) not in PRUNE_RELPATHS)
        for f in sorted(files):
            if f.endswith(suffixes):
                yield os.path.join(d, f)


def parse_tree(root: str = ROOT) -> tuple[list[str], dict]:
    bad, n = [], {".json": 0, ".toml": 0}
    for p in iter_data_files(root):
        ext = os.path.splitext(p)[1]
        try:
            if ext == ".json":
                with open(p, encoding="utf-8") as f:
                    json.load(f, object_pairs_hook=_no_duplicate_keys)
            else:
                _toml(p)
            n[ext] += 1
        except Exception as e:                                      # noqa: BLE001 - any parse error is a failure
            bad.append(f"{os.path.relpath(p, root)}: {type(e).__name__}: {e}")
    return bad, n


def check_parse_json_toml(root: str = ROOT):
    bad, n = parse_tree(root)
    if n[".json"] + n[".toml"] == 0:
        bad.append("no *.json / *.toml file found: wrong repository root?")
    return bad, f"{n['.json']} JSON + {n['.toml']} TOML files parsed"


# ------------------------------------------------------------------------------------------------------------ evidence pins
def check_prereg_lock(bridge_dir: str = BR):
    lock = _json(os.path.join(bridge_dir, "prereg", "p5_n2_prereg_lock_v1.json"))
    if not lock.get("files"):
        return ["prereg lock lists no files"], ""
    bad = verify_sha_map(bridge_dir, lock["files"], "prereg lock")
    crit = _json(os.path.join(bridge_dir, "prereg", "p5_n2_validation_criteria_v1.json"))
    pin = crit["inputs_pinned"]
    for k in ("measurement_audit", "cases", "transport_candidates"):
        bad += verify_sha_map(bridge_dir, {pin[k]["file"]: pin[k]["sha256"]}, f"criteria inputs_pinned.{k}")
    chem = pin["chemistry_configs_sha256"]
    bad += verify_sha_map(os.path.join(bridge_dir, "propellants"), chem, "criteria chemistry_configs_sha256")
    bad += [f"mandatory chemistry {c} has no pinned sha256" for c in crit.get("mandatory_chemistry", []) if c not in chem]
    return bad, f"{len(lock['files'])} locked files, 3 pinned inputs, {len(chem)} pinned chemistry configs"


def check_audit_manifest(bridge_dir: str = BR):
    d = os.path.join(bridge_dir, "audit", "configs")
    prop = os.path.join(bridge_dir, "propellants")
    man = _json(os.path.join(d, "MANIFEST.json"))
    bad = [] if man.get("configs") else ["MANIFEST lists no configs"]
    n_tables = 0
    for f, m in man.get("configs", {}).items():
        bad += verify_sha_map(d, {f: m["sha256"]}, "audit snapshot")
        if not os.path.isfile(os.path.join(d, f)):
            continue
        used = {r["rate_coeff_file"] for r in _toml(os.path.join(d, f)).get("reactions", [])}
        if used != set(m["rate_files"]):
            bad.append(f"audit snapshot {f}: rate files {sorted(used ^ set(m['rate_files']))} differ between snapshot and MANIFEST")
        bad += verify_sha_map(prop, m["rate_files"], f"audit snapshot {f} rate table")
        n_tables += len(m["rate_files"])
    for f, m in man.get("case_files", {}).items():
        bad += verify_sha_map(d, {f: m["sha256"]}, "audit case snapshot")
    return bad, (f"{len(man.get('configs', {}))} config snapshots, {n_tables} pinned rate-table references, "
                 f"{len(man.get('case_files', {}))} case snapshots")


def check_hallthruster_pin(bridge_dir: str = BR):
    pin = _toml(os.path.join(bridge_dir, "PINNED.toml"))["hallthruster"]
    man = _toml(os.path.join(bridge_dir, "Manifest.toml"))
    proj = _toml(os.path.join(bridge_dir, "Project.toml"))
    entries = man.get("deps", {}).get("HallThruster", [])
    if len(entries) != 1:
        return [f"Manifest.toml has {len(entries)} HallThruster entries (expected 1)"], ""
    e, bad = entries[0], []
    for mkey, pkey in (("repo-rev", "commit"), ("version", "version"), ("repo-url", "repository")):
        if e.get(mkey) != pin[pkey]:
            bad.append(f"Manifest.toml HallThruster {mkey} {e.get(mkey)!r} != PINNED.toml {pkey} {pin[pkey]!r}")
    compat = proj.get("compat", {}).get("HallThruster")
    if compat != "=" + pin["version"]:
        bad.append(f"Project.toml compat HallThruster {compat!r} != '={pin['version']}'")
    return bad, f"HallThruster.jl {pin['version']} @ {pin['commit'][:12]}"


def check_rate_validity_coverage(prop_dir: str = PROP):
    validity = _toml(os.path.join(prop_dir, "rate_validity.toml"))
    bad, n_cfg, used = [], 0, set()
    for name in sorted(os.listdir(prop_dir)):
        if not name.endswith(".toml") or name == "rate_validity.toml":
            continue
        n_cfg += 1
        for r in _toml(os.path.join(prop_dir, name)).get("reactions", []):
            f = r.get("rate_coeff_file")
            if f is None:
                bad.append(f"{name}: reaction without rate_coeff_file")
                continue
            used.add(f)
            if not os.path.isfile(os.path.join(prop_dir, f)):
                bad.append(f"{name}: rate file {f} is missing")
            v = validity.get(f)
            if v is None:
                bad.append(f"{name}: rate file {f} has no rate_validity.toml entry (a driver error, never a default)")
            elif v.get("status") == "verified":
                if not isinstance(v.get("max_mean_energy_eV"), (int, float)):
                    bad.append(f"rate_validity.toml [{f}]: verified without a numeric max_mean_energy_eV")
            elif v.get("status") != "unresolved":
                bad.append(f"rate_validity.toml [{f}]: status {v.get('status')!r} is neither verified nor unresolved")
    return sorted(set(bad)), f"{n_cfg} propellant configs, {len(used)} distinct rate files covered"


# ------------------------------------------------------------------------------------------------- fresh generation, no write
class _CapturedText(io.StringIO):
    def __init__(self, cap, key, encoding, newline):
        super().__init__()
        self._cap, self._key, self._enc, self._nl = cap, key, encoding, newline
        cap._open_bufs[key] = self

    def snapshot(self) -> bytes:
        s = self.getvalue()
        if self._nl is None and os.linesep != "\n":             # text-mode newline translation, as a real file would do
            s = s.replace("\n", os.linesep)
        elif self._nl not in (None, "", "\n"):
            s = s.replace("\n", self._nl)
        return s.encode(self._enc)

    def close(self):
        if not self.closed:
            self._cap.files[self._key] = self.snapshot()
            self._cap._open_bufs.pop(self._key, None)
        super().close()


class _CapturedBytes(io.BytesIO):
    def __init__(self, cap, key):
        super().__init__()
        self._cap, self._key = cap, key
        cap._open_bufs[key] = self

    def snapshot(self) -> bytes:
        return self.getvalue()

    def close(self):
        if not self.closed:
            self._cap.files[self._key] = self.snapshot()
            self._cap._open_bufs.pop(self._key, None)
        super().close()


class WriteCapture:
    """Context manager: code run inside has its file writes captured in memory (.files = {absolute path: bytes}); nothing
    reaches the disk. Reads pass through to the committed files. Append / update modes and moves / removals / copies raise."""

    _REFUSE = (("os", "replace"), ("os", "rename"), ("os", "renames"), ("os", "remove"), ("os", "unlink"), ("os", "rmdir"),
               ("os", "removedirs"), ("os", "truncate"), ("shutil", "rmtree"), ("shutil", "move"), ("shutil", "copy"),
               ("shutil", "copy2"), ("shutil", "copyfile"), ("shutil", "copytree"))

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self._open_bufs: dict = {}
        self._saved: list = []

    def _open(self, file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
        if isinstance(file, int) or not any(c in mode for c in "wax+"):
            return self._real_open(file, mode, buffering, encoding, errors, newline, closefd, opener)
        if any(c in mode for c in "ax+"):
            raise RuntimeError(f"WriteCapture: {file!r} opened in mode {mode!r}; only plain 'w' writes are captured")
        key = os.path.abspath(os.fspath(file))
        if "b" in mode:
            return _CapturedBytes(self, key)
        return _CapturedText(self, key, encoding or locale.getpreferredencoding(False), newline)

    @staticmethod
    def _refuse(name):
        def refused(*a, **k):
            raise RuntimeError(f"WriteCapture: {name}{a!r} refused (a generator under check must not move or remove files)")
        return refused

    @staticmethod
    def _no_mkdir(*a, **k):
        return None                                                 # never create directories in the tree

    def _patch(self, obj, name, value):
        self._saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def __enter__(self):
        self._real_open = builtins.open
        self._patch(builtins, "open", self._open)
        self._patch(io, "open", self._open)
        self._patch(os, "makedirs", self._no_mkdir)
        self._patch(os, "mkdir", self._no_mkdir)
        for modname, name in self._REFUSE:
            self._patch(os if modname == "os" else shutil, name, self._refuse(f"{modname}.{name}"))
        self._patch(sys, "dont_write_bytecode", True)
        return self

    def __exit__(self, *exc):
        for obj, name, value in reversed(self._saved):
            setattr(obj, name, value)
        self._saved.clear()
        for key, buf in list(self._open_bufs.items()):             # generators that never close their files: json.dump(open())
            self.files[key] = buf.snapshot()
        self._open_bufs.clear()
        return False


def run_generator(script: str, argv: tuple = ()) -> dict[str, bytes]:
    """Run scripts/<script> as __main__ (its own write path) under WriteCapture; return {absolute path: bytes}."""
    path = os.path.join(SCRIPTS, script)
    old_argv = sys.argv
    sys.argv = [path, *argv]
    try:
        with WriteCapture() as cap, contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(path, run_name="__main__")
    finally:
        sys.argv = old_argv
    return cap.files


def compare_with_committed(captured: dict[str, bytes], label: str) -> list[str]:
    if not captured:
        return [f"{label}: the generator produced no output"]
    bad = []
    for p, data in sorted(captured.items()):
        if not os.path.isfile(p):
            bad.append(f"{label}: {_rel(p)} would be generated but is not committed")
            continue
        with open(p, "rb") as f:
            committed = f.read()
        if committed != data:
            how = ""
            if p.endswith(".json"):
                try:
                    how = (" (parsed content equal: formatting only)" if json.loads(committed) == json.loads(data)
                           else " (content differs)")
                except ValueError:
                    pass
            bad.append(f"{label}: {_rel(p)} differs from a fresh generation{how}")
    return bad


def load_script(name: str):
    """Import scripts/<name>.py as a module (module-level code under WriteCapture)."""
    spec = importlib.util.spec_from_file_location(f"_ci_{name}", os.path.join(SCRIPTS, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    with WriteCapture():
        spec.loader.exec_module(m)
    return m


def check_variant_configs():
    cap = run_generator("make_n2_variant_configs.py")
    variants = load_script("make_n2_variant_configs").VARIANTS
    bad = compare_with_committed(cap, "variant configs")
    names = {os.path.basename(p) for p in cap}
    if names != set(variants) or any(os.path.dirname(p) != PROP for p in cap):
        bad.append(f"variant generator output {sorted(_rel(p) for p in cap)} does not match VARIANTS in propellants/")
    for p in sorted(os.listdir(PROP)):                              # no committed GENERATED VARIANT without a generator entry
        if p.endswith(".toml") and p not in variants:
            with open(os.path.join(PROP, p), encoding="utf-8") as f:
                if f.readline().startswith("# GENERATED VARIANT"):
                    bad.append(f"propellants/{p} is marked GENERATED VARIANT but is not in make_n2_variant_configs.VARIANTS")
    return bad, f"{len(cap)} variant configs regenerated in memory"


def check_p5_n2_cases():
    cap = run_generator("make_p5_n2_cases.py")
    target = os.path.join(BR, "cases", "p5_n2.json")
    bad = compare_with_committed(cap, "P5-N2 cases")
    if set(cap) != {target}:
        bad.append(f"make_p5_n2_cases.py wrote {sorted(_rel(p) for p in cap)}, expected only {_rel(target)}")
    n = len(json.loads(cap[target])["cases"]) if target in cap else 0
    return bad, f"{_rel(target)} regenerated in memory ({n} cases)"


def check_launch_manifests():
    cap = run_generator("make_p5_n2_launch_manifests.py")
    out = os.path.join(BR, "campaign", "manifests")
    bad = compare_with_committed(cap, "launch manifests")
    if any(os.path.dirname(p) != out for p in cap):
        bad.append("make_p5_n2_launch_manifests.py wrote outside campaign/manifests/")
    committed = {os.path.join(out, f) for f in os.listdir(out) if f.endswith(".json")} if os.path.isdir(out) else set()
    bad += [f"launch manifests: {_rel(p)} is committed but not produced by build()" for p in sorted(committed - set(cap))]
    return bad, f"{len(cap)} launch manifests rebuilt in memory (driver and prereg-lock sha256 included)"


def check_multiply_charged_tables():
    cap = run_generator("build_multiply_charged_tables.py")
    n_dat = sum(p.endswith(".dat") for p in cap)
    return compare_with_committed(cap, "multiply-charged tables"), f"{n_dat} tables + {len(cap) - n_dat} .source files rebuilt in memory"


# ------------------------------------------------------------------------------------------------------------ ensemble gate
def check_ensemble_gate():
    from abep_sim import hall_ensemble as he
    e = he.load_ensemble()
    members, screening = he.member_ids(e), he.screening_ids(e)
    bad = [f"ids both admitted and screening: {sorted(members & screening)}"] if members & screening else []
    for mid in sorted(screening):
        try:
            he.require_admitted(mid, e)
            bad.append(f"require_admitted accepted SCREENING candidate {mid}")
        except ValueError as err:
            if "SCREENING" not in str(err):
                bad.append(f"require_admitted refused {mid} for the wrong reason: {err}")
    try:
        he.require_admitted("ci-unknown-member-id", e)
        bad.append("require_admitted accepted an unknown id")
    except ValueError:
        pass
    return bad, f"ensemble loads; {len(members)} admitted, {len(screening)} screening candidates all refused by require_admitted"


# ------------------------------------------------------------------------------------------------------------ pytest outcome
def check_pytest_outcomes(junit_path: str):
    """CLAUDE.md rule 9 from a pytest --junitxml report: no failure or error, exactly EXPECTED_SKIPPED skips (all SUPERSEDED),
    xfails exactly EXPECTED_XFAIL (strict, so an unexpected pass is already a pytest failure)."""
    bad, skips, xfails, n = [], [], [], 0
    for tc in ET.parse(junit_path).iter("testcase"):
        n += 1
        name = tc.get("name", "")
        for el in tc:
            if el.tag in ("failure", "error"):
                bad.append(f"{tc.get('classname')}::{name}: {el.tag} {el.get('message', '')[:200]}")
            elif el.tag == "skipped":
                (xfails if el.get("type") == "pytest.xfail" else skips).append((name, el.get("message", "")))
    if n == 0:
        bad.append("the junit report contains no test case")
    if len(skips) != EXPECTED_SKIPPED:
        bad.append(f"{len(skips)} skipped tests, CLAUDE.md rule 9 expects {EXPECTED_SKIPPED}: {sorted(s for s, _ in skips)}")
    bad += [f"skip {s} is not a {EXPECTED_SKIP_REASON_PREFIX} retirement: {msg[:120]!r}" for s, msg in skips
            if not msg.startswith(EXPECTED_SKIP_REASON_PREFIX)]
    if sorted(x for x, _ in xfails) != sorted(EXPECTED_XFAIL):
        bad.append(f"xfailed tests {sorted(x for x, _ in xfails)}, CLAUDE.md rule 9 expects {sorted(EXPECTED_XFAIL)}")
    return bad, f"{n} tests: {len(skips)} skipped, {len(xfails)} xfailed"


CHECKS = {
    "parse_json_toml": check_parse_json_toml,
    "prereg_lock": check_prereg_lock,
    "audit_manifest": check_audit_manifest,
    "hallthruster_pin": check_hallthruster_pin,
    "rate_validity_coverage": check_rate_validity_coverage,
    "variant_configs": check_variant_configs,
    "p5_n2_cases": check_p5_n2_cases,
    "launch_manifests": check_launch_manifests,
    "multiply_charged_tables": check_multiply_charged_tables,
    "ensemble_gate": check_ensemble_gate,
}


def run_checks(names=None) -> dict[str, tuple[list[str], str]]:
    """{name: (problems, note)}; a check that raises is a failing check, never a skipped one."""
    res = {}
    for name in names or CHECKS:
        t0 = time.perf_counter()
        try:
            problems, note = CHECKS[name]()
        except Exception as e:                                      # noqa: BLE001
            problems, note = [f"check raised {type(e).__name__}: {e}"], ""
        res[name] = (problems, f"{note} [{time.perf_counter() - t0:.1f} s]".strip())
    return res


def _report(res: dict[str, tuple[list[str], str]]) -> int:
    for name, (problems, note) in res.items():
        print(f"[{'PASS' if not problems else 'FAIL'}] {name}: {note}")
        for p in problems:
            print(f"    - {p}")
    n_fail = sum(1 for p, _ in res.values() if p)
    print(f"ci_checks: {len(res) - n_fail}/{len(res)} passed")
    return 1 if n_fail else 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--list" in argv:
        print("\n".join(CHECKS))
        return 0
    if "--pytest-junit" in argv:
        i = argv.index("--pytest-junit")
        if i + 1 >= len(argv):
            print("usage: --pytest-junit PATH")
            return 2
        try:
            problems, note = check_pytest_outcomes(argv[i + 1])
        except (OSError, ET.ParseError) as e:
            problems, note = [f"cannot read junit report: {e}"], ""
        return _report({"pytest_outcomes": (problems, note)})
    names = None
    if "--only" in argv:
        i = argv.index("--only")
        names = argv[i + 1].split(",") if i + 1 < len(argv) else []
        unknown = [n for n in names if n not in CHECKS]
        if unknown or not names:
            print(f"unknown or missing check name(s) {unknown}; available: {', '.join(CHECKS)}")
            return 2
    return _report(run_checks(names))


if __name__ == "__main__":
    sys.dont_write_bytecode = True                                  # CLI: importing repository modules writes no __pycache__
    sys.exit(main())
