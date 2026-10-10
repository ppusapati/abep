"""Static repository-integrity checks for CI (docs/ci/CI.md). Fast (seconds), no Julia, no simulation, writes NO file.

Each check returns (problems, note): an empty problem list is a pass, the note says what was verified. The checks enforce the
evidence chain of CLAUDE.md / docs/EVIDENCE.md mechanically. They never change physics, thresholds, frozen data or chemistry,
and they never read campaign records (hallthruster_bridge/out/ and any run output are out of scope).

  parse_json_toml          every *.json and *.toml in the repository parses (a duplicate JSON key is an error), and every
                           non-empty line of every *.jsonl evidence ledger (docs/orchestration trigger ledgers, audit records)
                           is one JSON object; campaign run records under hallthruster_bridge/validation/ are not read
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
  h2_6_live_sources        review finding SW-02: the H2-6 builder's verify_sources() reports no consumed value that differs from
                           its live source (the builder is immutable H2 v1 history, so the gate lives here, not in its --check)
  bid_source_guard         A9.29 sec. 3: docs/bid/** equals the terminal package state 2de86ab (docs/bid/bid_source_manifest_v1.json
                           is the only added path), mission_scenario_v2 unchanged, and in git the lineage 5eee4b8 -> b5849af ->
                           2de86ab -> HEAD, the recorded tree ids and file hashes hold. Needs full history: in a shallow clone
                           the history part is NOT_EVALUATED and the check fails. Same semantics as the primary Rust guard
                           (crates/abep-provenance/src/bid_guard.rs; acceptance_v1.json in docs/rust_migration/contracts/)

"Fresh generation" runs each generator's OWN write path (its __main__, default arguments) inside WriteCapture: builtins.open /
io.open in a writing mode return in-memory buffers, directory creation is a no-op, every move / remove / copy call raises and
no bytecode is cached, so nothing reaches the disk. The captured bytes are compared with the committed files.

Separate mode, used by CI after pytest (CLAUDE.md rule 9: all pass, 5 skipped = the SUPERSEDED 0-D Hall calibration, 1 strict
xfail = test_v16_blind_validation_p5_nitrogen):
  python scripts/ci_checks.py --pytest-junit report.xml
Rule 9 holds only in a FULL-HISTORY clone: several provenance tests (e.g. tests/test_bundle1.py, tests/test_echt_status.py,
tests/test_v2_question_a_brief.py) resolve pinned lane commits with `git show` and skip when those objects are absent, as in a
shallow (depth-1) checkout. This mode therefore also fails, with an explicit reason, when the repository is shallow.

Separate mode, used once for the bid_source_guard acceptance report (writes only temporary directories, removed after):
  python scripts/ci_checks.py --bid-guard-acceptance       JSON results of every preregistered case on stdout

Usage: python scripts/ci_checks.py [--list] [--only NAME[,NAME...]] [--pytest-junit PATH] [--bid-guard-acceptance]
       exit 0 pass, 1 fail, 2 usage
"""
from __future__ import annotations

import builtins, contextlib, hashlib, importlib.util, io, json, locale, os, runpy, shutil, stat, subprocess, sys, tempfile
import time, tomllib
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
# *.jsonl: parsed line by line, except campaign run records (CI never reads campaign records; their integrity is bound by the
# validation release pipeline, hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json and its own scripts).
JSONL_SKIP_RELPATHS = {os.path.join("hallthruster_bridge", "validation")}
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


def iter_data_files(root: str = ROOT, suffixes=(".json", ".toml", ".jsonl")):
    for d, dirs, files in os.walk(root):
        rel_d = os.path.relpath(d, root)
        dirs[:] = sorted(x for x in dirs if x not in PRUNE_NAMES and not x.endswith(".egg-info")
                         and os.path.normpath(os.path.join(rel_d, x)) not in PRUNE_RELPATHS)
        for f in sorted(files):
            if not f.endswith(suffixes):
                continue
            if f.endswith(".jsonl") and any(os.path.normpath(os.path.join(rel_d, f)).startswith(p + os.sep)
                                            for p in JSONL_SKIP_RELPATHS):
                continue
            yield os.path.join(d, f)


def parse_tree(root: str = ROOT) -> tuple[list[str], dict]:
    bad, n = [], {".json": 0, ".toml": 0, ".jsonl": 0}
    for p in iter_data_files(root):
        ext = os.path.splitext(p)[1]
        try:
            if ext == ".json":
                with open(p, encoding="utf-8") as f:
                    json.load(f, object_pairs_hook=_no_duplicate_keys)
            elif ext == ".jsonl":
                with open(p, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if line.strip():
                            try:
                                obj = json.loads(line, object_pairs_hook=_no_duplicate_keys)
                            except ValueError as e:
                                raise ValueError(f"line {i}: {e}") from None
                            if not isinstance(obj, dict):
                                raise ValueError(f"line {i}: not a JSON object")
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
    return bad, f"{n['.json']} JSON + {n['.toml']} TOML + {n['.jsonl']} JSONL files parsed"


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


# ------------------------------------------------------------------------------------------------------- H2-6 live sources
H2_6_BUILDER = os.path.join(ROOT, "docs", "hardware", "h2", "h2_6_diagnostics_fixture", "build_h2_6_diagnostics_fixture.py")


def load_h2_6():
    """The H2-6 builder (immutable H2 v1 history, A9.10 reconciliation) imported read-only (module code under WriteCapture)."""
    spec = importlib.util.spec_from_file_location("_ci_h2_6", H2_6_BUILDER)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    with WriteCapture():
        spec.loader.exec_module(m)
    return m


def check_h2_6_live_sources():
    """Review finding SW-02: every value the H2-6 deliverable consumed still equals its live source (verify_sources), so a
    regenerated upstream (e.g. the W1 feed-state closure) can never leave a stale transcription passing CI. Runs here
    because the H2-6 builder itself is immutable H2 v1 history (byte-identical to the A9.10 reconciliation base)."""
    m = load_h2_6()
    with WriteCapture():
        bad = list(m.verify_sources())
    return bad, f"{_rel(H2_6_BUILDER)} verify_sources(): consumed values == live sources"


# ------------------------------------------------------------------------------------------------------- bid source guard
# A9.29 sec. 3 (RM-OQ-11), CI_PLAN.md § 3. Semantics, codes and tamper cases are preregistered in BID_ACCEPTANCE; the
# primary implementation is Rust (crates/abep-provenance/src/bid_guard.rs). Same manifest, same codes.
BID_TECHNICAL_SOURCE = "5eee4b8c82a9403b6bb82d5f8d324526f5d6399b"
BID_TERMINAL = "2de86abefacbd36ce7516d3cf017f6258bd7e7a2"
BID_LINEAGE = ["b5849affae22a6709ad217a184f6fe896d15410a", BID_TERMINAL]
BID_MISSION_PATH = "config/mission/mission_scenario_v2.json"
BID_MISSION_SHA256 = "885b1f70a1a44389e088837fd37bb79390b63132e3c81f17923103b2f9b5fc49"
BID_MANIFEST_PATH = "docs/bid/bid_source_manifest_v1.json"
BID_MANIFEST_SCHEMA = "abep_bid_source_manifest_v1"
BID_ROOT = "docs/bid/"
BID_BASELINE = "docs/bid/bid_technical_baseline_v2.json"
BID_IGNORED_PATTERN = "**/__pycache__/*.pyc"
BID_DECISION_PREFIX = "docs/decisions/OD_"
BID_ACCEPTANCE = "docs/rust_migration/contracts/BID_SOURCE_GUARD/acceptance_v1.json"
BID_ACCEPTANCE_SHA256 = "8d23e1f16d63dcbe2ce27f1ad48712d118808270d0ae5ab2ab2a2a6eb60ab1c6"


class _GitError(Exception):
    pass


def _is_hex(s, n: int) -> bool:
    return isinstance(s, str) and len(s) == n and all(c in "0123456789abcdef" for c in s)


def _safe_rel(p) -> bool:
    return (isinstance(p, str) and p != "" and not p.startswith("/") and "\\" not in p
            and all(seg not in ("", ".", "..") for seg in p.split("/")))


def _field(v, key):
    if not isinstance(v, dict) or key not in v:
        raise ValueError(f"missing field {key}")
    return v[key]


def _str_field(v, key) -> str:
    s = _field(v, key)
    if not isinstance(s, str):
        raise ValueError(f"field {key} is not a string")
    return s


def _hex_field(v, key, n) -> str:
    s = _str_field(v, key)
    if not _is_hex(s, n):
        raise ValueError(f"field {key} is not {n} lower-case hex digits")
    return s


def _bid_file_map(v, key, prefix) -> dict:
    obj = _field(v, key)
    if not isinstance(obj, dict) or not obj:
        raise ValueError(f"field {key} is not a non-empty object")
    out = {}
    for path, rec in obj.items():
        if not _safe_rel(path) or not path.startswith(prefix):
            raise ValueError(f"{key}: path {path!r} is not a safe relative path under {prefix!r}")
        sha = _hex_field(rec, "sha256", 64)
        n = rec.get("bytes")
        if "bytes" in rec and not (type(n) is int and 0 <= n < 2 ** 64):
            raise ValueError(f"{key}[{path}]: bytes is not a non-negative integer")
        out[path] = (sha, n)
    return out


def bid_parse_manifest(data: bytes) -> dict:
    v = json.loads(data)
    if _str_field(v, "schema") != BID_MANIFEST_SCHEMA:
        raise ValueError(f"schema is not {BID_MANIFEST_SCHEMA}")
    ts = _field(v, "technical_source")
    lineage_v = _field(v, "package_lineage")
    if not isinstance(lineage_v, list) or not lineage_v:
        raise ValueError("package_lineage is not a non-empty list")
    lineage = [{"commit": _hex_field(e, "commit", 40), "docs_bid_tree": _hex_field(e, "docs_bid_tree", 40),
                "files": _bid_file_map(e, "files", BID_ROOT)} for e in lineage_v]
    mission = _field(v, "mission_scenario_v2")
    ignored = _field(v, "ignored_generated_artifacts")
    if not isinstance(ignored, list) or [x.get("pattern") if isinstance(x, dict) else None
                                         for x in ignored] != [BID_IGNORED_PATTERN]:
        raise ValueError(f"ignored_generated_artifacts must be exactly [{BID_IGNORED_PATTERN}]")
    auths = _field(v, "owner_change_authorizations")
    if not isinstance(auths, list):
        raise ValueError("owner_change_authorizations is not a list")
    return {"technical_source": _hex_field(ts, "commit", 40), "technical_source_tree": _hex_field(ts, "tree", 40),
            "technical_source_files": _bid_file_map(ts, "files", ""), "lineage": lineage,
            "terminal": _hex_field(_field(v, "terminal_package_state"), "commit", 40),
            "manifest_path": _str_field(v, "manifest_path"), "mission_path": _str_field(mission, "path"),
            "mission_sha256": _hex_field(mission, "sha256", 64), "authorizations": auths}


def _finding(code, path, detail):
    return {"code": code, "path": path, "detail": detail}


def _part(findings):
    findings = sorted(findings, key=lambda f: (f["code"], f["path"], f["detail"]))
    return {"status": "FAIL" if findings else "PASS", "findings": findings}


def _not_evaluated(detail):
    return {"status": "NOT_EVALUATED", "findings": [_finding("HISTORY_NOT_AVAILABLE", "", detail)]}


def _compare(rec, data: bytes):
    sha, n = rec
    got = hashlib.sha256(data).hexdigest()
    if got != sha:
        return f"sha256 {got} != {sha}"
    if n is not None and n != len(data):
        return f"{len(data)} bytes != {n}"
    return None


def _bid_validate_authorization(a, root, protected, claimed):
    rec = _field(a, "decision_record")
    rpath = _str_field(rec, "path")
    rsha = _hex_field(rec, "sha256", 64)
    if not rpath.startswith(BID_DECISION_PREFIX) or not _safe_rel(rpath):
        raise ValueError(f"decision record {rpath!r} is not under {BID_DECISION_PREFIX}")
    try:
        with open(os.path.join(root, rpath), "rb") as f:
            data = f.read()
    except OSError as e:
        raise ValueError(f"decision record {rpath}: {e}") from None
    if hashlib.sha256(data).hexdigest() != rsha:
        raise ValueError(f"decision record {rpath}: sha256 differs from the authorization")
    changes = _field(a, "changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("changes is not a non-empty list")
    out, seen = [], set()
    for c in changes:
        path, action = _str_field(c, "path"), _str_field(c, "action")
        if not _safe_rel(path) or not path.startswith(BID_ROOT) or path == BID_MANIFEST_PATH:
            raise ValueError(f"{path!r} is not an authorizable docs/bid path")
        if path in claimed or path in seen:
            raise ValueError(f"{path} is authorized twice")
        seen.add(path)
        if action in ("MODIFY", "ADD"):
            if (action == "MODIFY") != (path in protected):
                raise ValueError(f"{action} of {path}: protected = {path in protected}")
            after = c.get("sha256_after")
            if not _is_hex(after, 64):
                raise ValueError(f"{action} of {path} needs a 64-hex sha256_after")
            out.append((path, (after, None)))
        elif action == "REMOVE":
            if path not in protected:
                raise ValueError(f"REMOVE of {path}: not a protected file")
            if "sha256_after" in c:
                raise ValueError(f"REMOVE of {path} carries sha256_after")
            out.append((path, None))
        else:
            raise ValueError(f"action {action!r} is not MODIFY / ADD / REMOVE")
    return out


def _bid_files_part(root, m):
    """F-01..F-08 on the working tree; returns (part, expected {path: (sha256, bytes) | None = absent})."""
    out = []
    for ok, field, detail in (
            (m["technical_source"] == BID_TECHNICAL_SOURCE, "technical_source.commit", m["technical_source"]),
            (m["terminal"] == BID_TERMINAL, "terminal_package_state.commit", m["terminal"]),
            ([e["commit"] for e in m["lineage"]] == BID_LINEAGE, "package_lineage", "lineage commits"),
            (m["lineage"][-1]["commit"] == m["terminal"], "terminal_package_state.commit", "not the last lineage entry"),
            (m["mission_path"] == BID_MISSION_PATH, "mission_scenario_v2.path", m["mission_path"]),
            (m["mission_sha256"] == BID_MISSION_SHA256, "mission_scenario_v2.sha256", m["mission_sha256"]),
            (m["manifest_path"] == BID_MANIFEST_PATH, "manifest_path", m["manifest_path"])):
        if not ok:
            out.append(_finding("LINEAGE_RECORD_MISMATCH", field, detail))
    protected = m["lineage"][-1]["files"]
    expected = dict(protected)
    claimed = set()
    for i, a in enumerate(m["authorizations"]):
        try:
            changes = _bid_validate_authorization(a, root, protected, claimed)
        except ValueError as e:
            out.append(_finding("AUTHORIZATION_INVALID", f"owner_change_authorizations[{i}]", str(e)))
            continue
        for path, e in changes:
            claimed.add(path)
            expected[path] = e
    for path, rec in expected.items():
        p = os.path.join(root, path)
        try:
            st = os.lstat(p)
        except OSError:
            if rec is not None:
                out.append(_finding("BID_FILE_MISSING", path, "absent from the working tree"))
            continue
        if rec is None:
            out.append(_finding("BID_FILE_UNLISTED", path, "removed by authorization but present"))
        elif not stat.S_ISREG(st.st_mode):
            out.append(_finding("BID_FILE_MODIFIED", path, "not a regular file"))
        else:
            with open(p, "rb") as f:
                diff = _compare(rec, f.read())
            if diff:
                out.append(_finding("BID_FILE_MODIFIED", path, diff))
    for rel, is_file in _bid_walk(root, BID_ROOT.rstrip("/")):
        parts = rel.split("/")
        ignored = is_file and len(parts) > 1 and parts[-2] == "__pycache__" and parts[-1].endswith(".pyc")
        if rel in expected or rel == BID_MANIFEST_PATH or ignored:
            continue
        out.append(_finding("BID_FILE_UNLISTED", rel, "not a file of the terminal package state"))
    try:
        with open(os.path.join(root, BID_MISSION_PATH), "rb") as f:
            got = hashlib.sha256(f.read()).hexdigest()
        if got != BID_MISSION_SHA256:
            out.append(_finding("MISSION_SCENARIO_CHANGED", BID_MISSION_PATH, f"sha256 {got}"))
    except OSError as e:
        out.append(_finding("MISSION_SCENARIO_CHANGED", BID_MISSION_PATH, f"unreadable: {e}"))
    try:
        with open(os.path.join(root, BID_BASELINE), "rb") as f:
            src = json.loads(f.read()).get("bid_technical_source")
        pin = src.get("commit") if isinstance(src, dict) else None
    except (OSError, ValueError, AttributeError):
        pin = None
    if pin != BID_TECHNICAL_SOURCE:
        out.append(_finding("TECHNICAL_SOURCE_PIN_CHANGED", BID_BASELINE, f"bid_technical_source.commit = {pin!r}"))
    return _part(out), expected


def _bid_walk(root, rel):
    try:
        names = sorted(os.listdir(os.path.join(root, rel)))
    except OSError:
        return []
    out = []
    for n in names:
        r = f"{rel}/{n}"
        try:
            st = os.lstat(os.path.join(root, r))
        except OSError:
            out.append((r, False))
            continue
        if stat.S_ISDIR(st.st_mode):
            out += _bid_walk(root, r)
        else:
            out.append((r, stat.S_ISREG(st.st_mode)))
    return out


_GIT_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")


def _git_run(repo, args, input_bytes=None):
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_DROP}
    return subprocess.run(["git", "-C", repo, *args], input=input_bytes, capture_output=True, env=env)


def _git_cat_file(repo, requests, with_content):
    if not requests:
        return []
    r = _git_run(repo, ["cat-file", "--batch" if with_content else "--batch-check"],
                 "".join(q + "\n" for q in requests).encode())
    if r.returncode != 0:
        raise _GitError(f"git cat-file exited with {r.returncode}")
    raw, pos, out = r.stdout, 0, []
    for _ in requests:
        end = raw.index(b"\n", pos)
        header = raw[pos:end].decode("utf-8", "replace")
        pos = end + 1
        if header.endswith((" missing", " ambiguous")):
            out.append(None)
            continue
        oid, kind, size = header.split(" ")
        content = None
        if with_content:
            content = raw[pos:pos + int(size)]
            pos += int(size) + 1
        out.append((oid, kind, content))
    return out


def _git_ls_tree(repo, rev, path):
    r = _git_run(repo, ["ls-tree", "-r", "-z", "--full-tree", rev, path])
    if r.returncode != 0:
        raise _GitError(f"git ls-tree {rev} {path}: {r.stderr.decode(errors='replace').strip()}")
    out = {}
    for rec in r.stdout.split(b"\0"):
        if rec:
            meta, name = rec.decode("utf-8", "replace").split("\t", 1)
            out[name] = meta.split(" ")[2]
    return out


def _git_is_ancestor(repo, a, b):
    r = _git_run(repo, ["merge-base", "--is-ancestor", a, b])
    if r.returncode not in (0, 1):
        raise _GitError(f"git merge-base --is-ancestor {a} {b}: {r.stderr.decode(errors='replace').strip()}")
    return r.returncode == 0


def _bid_history_part(repo, head, m, expected):
    """H-00..H-07 against a full-history repository (repo None = no history: NOT_EVALUATED)."""
    if repo is None:
        return _not_evaluated("no git repository given")
    try:
        r = _git_run(repo, ["rev-parse", "--is-shallow-repository"])
    except OSError as e:
        return _not_evaluated(f"cannot run git: {e}")
    if r.returncode != 0:
        return _not_evaluated(f"not a git repository: {r.stderr.decode(errors='replace').strip()}")
    flag = r.stdout.decode().strip()
    if flag == "true":
        return _not_evaluated("shallow clone: the lineage cannot be verified; fetch full history "
                              "(actions/checkout fetch-depth: 0)")
    if flag != "false":
        return _part([_finding("GIT_ERROR", "", f"rev-parse --is-shallow-repository printed {flag!r}")])
    try:
        return _part(_bid_history_checks(repo, head, m, expected))
    except (_GitError, OSError, ValueError) as e:
        return _part([_finding("GIT_ERROR", "", str(e))])


def _bid_history_checks(repo, head, m, expected):
    out = []
    revs = [("technical_source.commit", m["technical_source"])]
    revs += [(f"package_lineage[{i}].commit", e["commit"]) for i, e in enumerate(m["lineage"])]
    revs += [("terminal_package_state.commit", m["terminal"]), ("head", head)]
    for (label, rev), item in zip(revs, _git_cat_file(repo, [f"{r}^{{commit}}" for _, r in revs], False)):
        if item is None:
            out.append(_finding("GIT_ERROR" if label == "head" else "LINEAGE_COMMIT_MISSING", label,
                                f"{rev} is not a commit of this repository"))
    if out:
        return out
    lineage = m["lineage"]
    pairs = [(m["technical_source"], lineage[0]["commit"])]
    pairs += [(a["commit"], b["commit"]) for a, b in zip(lineage, lineage[1:])]
    pairs.append((m["terminal"], head))
    for a, b in pairs:
        if not _git_is_ancestor(repo, a, b):
            out.append(_finding("LINEAGE_ANCESTRY_BROKEN", f"{a}..{b}", f"{a} is not an ancestor of {b}"))
    trees = [(f"{m['technical_source']}^{{tree}}", m["technical_source_tree"])]
    trees += [(f"{e['commit']}:docs/bid", e["docs_bid_tree"]) for e in lineage]
    for (req, want), item in zip(trees, _git_cat_file(repo, [t for t, _ in trees], False)):
        got = item[0] if item else "missing"
        if got != want:
            out.append(_finding("TREE_HASH_MISMATCH", req, f"{got} != recorded {want}"))
    reqs, lineage_trees = [], []
    for e in lineage:
        t = _git_ls_tree(repo, e["commit"], BID_ROOT.rstrip("/"))
        for p in sorted(set(t) ^ set(e["files"])):
            out.append(_finding("LINEAGE_FILES_MISMATCH", p, f"file sets differ at {e['commit']}"))
        lineage_trees.append(t)
    head_tree = _git_ls_tree(repo, head, BID_ROOT.rstrip("/"))
    for e, t in zip(lineage, lineage_trees):
        reqs += [t[p] for p in sorted(e["files"]) if p in t]
    reqs += [f"{m['technical_source']}:{p}" for p in sorted(m["technical_source_files"])]
    reqs += [head_tree[p] for p in sorted(expected) if expected[p] is not None and p in head_tree]
    reqs.append(f"{head}:{BID_MISSION_PATH}")
    items = iter(_git_cat_file(repo, reqs, True))

    def nxt():
        it = next(items, None)
        return it[2] if it is not None and it[1] == "blob" else None

    for e, t in zip(lineage, lineage_trees):
        for p in sorted(e["files"]):
            if p not in t:
                continue
            d = nxt()
            diff = _compare(e["files"][p], d) if d is not None else f"unreadable at {e['commit']}"
            if diff:
                out.append(_finding("LINEAGE_FILES_MISMATCH", p, f"at {e['commit']}: {diff}"))
    for p in sorted(m["technical_source_files"]):
        d = nxt()
        diff = _compare(m["technical_source_files"][p], d) if d is not None else "absent at the technical source"
        if diff:
            out.append(_finding("TECHNICAL_SOURCE_FILE_MISMATCH", p, diff))
    for p in sorted(expected):
        rec = expected[p]
        if rec is not None and p in head_tree:
            d = nxt()
            diff = _compare(rec, d) if d is not None else f"unreadable at {head}"
            if diff:
                out.append(_finding("BID_FILE_MODIFIED", p, f"committed at {head}: {diff}"))
        elif rec is not None:
            out.append(_finding("BID_FILE_MISSING", p, f"not committed at {head}"))
        elif p in head_tree:
            out.append(_finding("BID_FILE_UNLISTED", p, f"removed by authorization but committed at {head}"))
    for p in sorted(head_tree):
        if p not in expected and p != BID_MANIFEST_PATH:
            out.append(_finding("BID_FILE_UNLISTED", p, f"committed at {head}, not a terminal package file"))
    d = nxt()
    if d is None:
        out.append(_finding("MISSION_SCENARIO_CHANGED", BID_MISSION_PATH, f"absent at {head}"))
    elif hashlib.sha256(d).hexdigest() != BID_MISSION_SHA256:
        out.append(_finding("MISSION_SCENARIO_CHANGED", BID_MISSION_PATH, f"committed at {head}: sha256 differs"))
    return out


def bid_source_guard(tree_root: str = ROOT, history_repo: str | None = ROOT, head: str = "HEAD") -> dict:
    """{overall, files, history}: overall FAIL if a part fails, NOT_EVALUATED if history is, PASS only if both pass."""
    try:
        with open(os.path.join(tree_root, BID_MANIFEST_PATH), "rb") as f:
            m = bid_parse_manifest(f.read())
    except (OSError, ValueError) as e:
        bad = _part([_finding("MANIFEST_INVALID", BID_MANIFEST_PATH, str(e))])
        return {"overall": "FAIL", "files": bad, "history": dict(bad)}
    files, expected = _bid_files_part(tree_root, m)
    history = _bid_history_part(history_repo, head, m, expected)
    if "FAIL" in (files["status"], history["status"]):
        overall = "FAIL"
    else:
        overall = "NOT_EVALUATED" if history["status"] == "NOT_EVALUATED" else "PASS"
    return {"overall": overall, "files": files, "history": history}


def check_bid_source_guard(root: str = ROOT):
    """A9.29 sec. 3: docs/bid/** equals the terminal package state 2de86ab (only the manifest added), mission_scenario_v2
    unchanged, lineage 5eee4b8 -> b5849af -> 2de86ab -> HEAD verified in git. Needs a full-history clone."""
    r = bid_source_guard(root, root, "HEAD")
    bad = [f"{part} {r[part]['status']}: {f['code']} {f['path']}: {f['detail']}"
           for part in ("files", "history") for f in r[part]["findings"]] if r["overall"] != "PASS" else []
    return bad, (f"overall {r['overall']} (files {r['files']['status']}, history {r['history']['status']}): terminal "
                 f"package state {BID_TERMINAL[:7]}, technical source {BID_TECHNICAL_SOURCE[:7]}, "
                 f"mission_scenario_v2 {BID_MISSION_SHA256[:8]}")


def _json_pointer_slot(doc, pointer):
    parts = [p.replace("~1", "/").replace("~0", "~") for p in pointer.split("/")[1:]]
    cur = doc
    for p in parts[:-1]:
        cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    last = parts[-1]
    return cur, (int(last) if isinstance(cur, list) else last)


def _bid_apply(dest, op):
    kind = op["op"]
    if kind in ("manifest_set", "manifest_reverse"):
        p = os.path.join(dest, BID_MANIFEST_PATH)
        with open(p, "rb") as f:
            doc = json.loads(f.read())
        parent, key = _json_pointer_slot(doc, op["pointer"])
        parent[key]                                                 # KeyError / IndexError: the pointer must exist
        if kind == "manifest_set":
            parent[key] = op["value"]
        else:
            parent[key].reverse()
        with open(p, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1)
        return
    p = os.path.join(dest, op["path"])
    if kind == "append_bytes":
        with open(p, "ab") as f:
            f.write(bytes.fromhex(op["hex"]))
    elif kind == "delete":
        os.remove(p)
    elif kind == "create":
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(op["text"].encode("utf-8"))
    elif kind == "replace_all":
        with open(p, "rb") as f:
            text = f.read().decode("utf-8")
        with open(p, "wb") as f:
            f.write(text.replace(op["old"], op["new"]).encode("utf-8"))
    else:
        raise ValueError(f"unknown op {kind}")


def _bid_scratch_repos(base):
    full = os.path.join(base, "full")
    _git_ok(base, ["init", "-q", "full"])
    for i in range(2):
        with open(os.path.join(full, "f.txt"), "w", encoding="utf-8") as f:
            f.write(f"{i}\n")
        _git_ok(full, ["add", "f.txt"])
        _git_ok(full, ["-c", "user.name=abep-acceptance", "-c", "user.email=abep-acceptance@invalid",
                       "-c", "commit.gpgsign=false", "commit", "-q", "-m", "scratch"])
    _git_ok(base, ["clone", "-q", "--depth", "1", f"file://{full}", "shallow"])
    return full, os.path.join(base, "shallow")


def _git_ok(repo, args):
    r = _git_run(repo, args)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.decode(errors='replace').strip()}")


def bid_case_summary(case_id, r):
    part = lambda p: {"status": p["status"], "codes": sorted({f["code"] for f in p["findings"]})}  # noqa: E731
    return {"id": case_id, "overall": r["overall"], "files": part(r["files"]), "history": part(r["history"])}


def bid_expectation_problems(case, r):
    e, problems = case["expected"], []
    for what, got in (("overall", r["overall"]), ("files", r["files"]["status"]), ("history", r["history"]["status"])):
        if got != e[what]:
            problems.append(f"{what} {got}, expected {e[what]}")
    for part in ("files", "history"):
        got = {f["code"] for f in r[part]["findings"]}
        problems += [f"{part}: required code {c} not reported (got {sorted(got)})"
                     for c in e["required_codes"][part] if c not in got]
    return problems


def bid_guard_acceptance(root: str = ROOT) -> list[dict]:
    """Run every preregistered case (BID_ACCEPTANCE, sha256-pinned): [{id, summary, problems, report}]. Writes only
    temporary directories, removed afterwards."""
    with open(os.path.join(root, BID_ACCEPTANCE), "rb") as f:
        data = f.read()
    if hashlib.sha256(data).hexdigest() != BID_ACCEPTANCE_SHA256:
        raise ValueError(f"{BID_ACCEPTANCE} differs from its preregistered sha256")
    cases = json.loads(data)["acceptance_cases"]["cases"]
    with open(os.path.join(root, BID_MANIFEST_PATH), "rb") as f:
        terminal_files = sorted(json.loads(f.read())["package_lineage"][-1]["files"])
    results = []
    with tempfile.TemporaryDirectory(prefix="abep-bidguard-") as tmp:
        full, shallow = _bid_scratch_repos(tmp)
        for n, case in enumerate(cases):
            tree = root
            if case["tree"] == "COPY":
                tree = os.path.join(tmp, f"case{n}")
                for p in terminal_files + [BID_MANIFEST_PATH, BID_MISSION_PATH]:
                    os.makedirs(os.path.dirname(os.path.join(tree, p)), exist_ok=True)
                    shutil.copyfile(os.path.join(root, p), os.path.join(tree, p))
                for op in case["tamper"]:
                    _bid_apply(tree, op)
            elif case["tree"] != "REPOSITORY" or case["tamper"]:
                raise ValueError(f"{case['id']}: invalid tree / tamper combination")
            repo = {"REPOSITORY": root, "NONE": None, "SCRATCH_SHALLOW": shallow, "SCRATCH_FULL": full}[case["history"]]
            r = bid_source_guard(tree, repo, case["head"])
            results.append({"id": case["id"], "summary": bid_case_summary(case["id"], r),
                            "problems": bid_expectation_problems(case, r), "report": r})
    return results


# ------------------------------------------------------------------------------------------------------------ pytest outcome
def check_full_history(root: str = ROOT) -> list[str]:
    """Rule 9 is defined on a full-history clone (history-dependent provenance tests skip otherwise). [] = full history."""
    try:
        r = subprocess.run(["git", "-C", root, "rev-parse", "--is-shallow-repository"], capture_output=True, text=True,
                           timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return [f"cannot determine git history depth ({type(e).__name__}: {e}); the rule-9 outcome needs a full-history clone"]
    if r.returncode != 0:
        return [f"not a git repository ({r.stderr.strip()[:200]}); the rule-9 outcome needs a full-history clone"]
    if r.stdout.strip() == "true":
        return ["shallow clone: provenance tests that resolve pinned lane commits skip, so the rule-9 skip count is not "
                "meaningful; check out with full history (actions/checkout fetch-depth: 0)"]
    return []


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
    "h2_6_live_sources": check_h2_6_live_sources,
    "bid_source_guard": check_bid_source_guard,
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
    if "--bid-guard-acceptance" in argv:
        results = bid_guard_acceptance()
        print(json.dumps({"implementation": "python", "python": sys.version.split()[0],
                          "cases": [r["summary"] for r in results],
                          "problems": {r["id"]: r["problems"] for r in results if r["problems"]}}, indent=1))
        return 1 if any(r["problems"] for r in results) else 0
    if "--pytest-junit" in argv:
        i = argv.index("--pytest-junit")
        if i + 1 >= len(argv):
            print("usage: --pytest-junit PATH")
            return 2
        try:
            problems, note = check_pytest_outcomes(argv[i + 1])
        except (OSError, ET.ParseError) as e:
            problems, note = [f"cannot read junit report: {e}"], ""
        problems = check_full_history() + problems
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
