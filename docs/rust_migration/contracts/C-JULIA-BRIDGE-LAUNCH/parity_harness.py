#!/usr/bin/env python3
"""Parity harness of C-JULIA-BRIDGE-LAUNCH v1 (parity_prereg_v1.json in this directory).

Executes every registered step with the Python reference (scripts/make_p5_n2_launch_manifests.py build / check, the
committed manifest commands as the runner scripts execute them, julia-smoke.yml's pin read / NJOBS / smoke command,
scripts/ci_checks.py check_hallthruster_pin) and with the Rust binary `abep-julia-bridge cases`, on byte-identical
case trees, and compares the outcomes. No Julia process is started.

  python3 -B parity_harness.py develop     development seed; never a verdict
  python3 -B parity_harness.py score       the single scoring execution: parity_report_v1.json + .md + reference_outputs/
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CONTRACT = os.path.join(HERE, "parity_prereg_v1.json")
REPORT_JSON = os.path.join(HERE, "parity_report_v1.json")
REPORT_MD = os.path.join(HERE, "parity_report_v1.md")
REF_DIR = os.path.join(HERE, "reference_outputs")
BIN = os.path.join(REPO, "target", "debug", "abep-julia-bridge")
PASS_THROUGH = ("HOME", "JULIA_DEPOT_PATH", "PATH", "TMPDIR")
THREAD_VARS = ("JULIA_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")
MESSAGE_KINDS = {"KEY_ERROR", "FILE_NOT_FOUND"}
FORBIDDEN = ["LaB6Cathode", "lab6_xe", "cathode_life", "XE_CATHODE", "hall_1stage", "mw_air", "rf_cathode",
             "CONTROL_FALLBACK", "keeper", "heater", "hollow", "cathode"]
RUST_SOURCES = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/abep-types/src/lib.rs",
                "crates/abep-provenance/src/lib.rs", "crates/abep-hall/Cargo.toml", "crates/abep-julia-bridge/Cargo.toml"]


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    with open(p, "rb") as f:
        return sha_bytes(f.read())


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def run(cmd, cwd=REPO, check=True, stdin=None):
    r = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd} failed: {r.stderr[-2000:]}")
    return r


def module(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


MM = module("scripts/make_p5_n2_launch_manifests.py", "mm_ref")
CI = module("scripts/ci_checks.py", "ci_ref")
CONTRACT_DOC = load(CONTRACT)
PIN = tomllib.load(open(os.path.join(REPO, "hallthruster_bridge/PINNED.toml"), "rb"))["hallthruster"]["commit"]
BOUNDARY_PIN = load(os.path.join(REPO, "docs/rust_migration/simulation_completion_programme_v1_1.json"))[
    "hall_physics_boundary"]["pin"]


def U(master, tag):
    return int.from_bytes(hashlib.sha256(f"{master}|{tag}".encode()).digest()[:8], "big")


# ------------------------------------------------------------------------------------------------------------- trees
def committed(name):
    return load(os.path.join(REPO, "hallthruster_bridge/campaign/manifests", f"{name}.json"))


def write_records(d, spec):
    m = committed(spec["manifest"])
    recs = [{"key": k, "mode": m["mode"], "smoke": False, "prereg_lock_sha256": m["prereg_lock_sha256"],
             "hallthruster_commit": PIN, "retcode": "success", "evidence_status": "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE"}
            for k in m["expected_keys"]]
    blank = False
    if spec.get("original_indices"):
        # interpretation note IN-01 (case CK-15): indices refer to the unmutated set
        orig = list(recs)
        muts = []
        for mu in spec["mutations"]:
            if mu[0] == "drop":
                muts.append(["drop_obj", orig[mu[1]]])
            elif len(mu) > 1 and isinstance(mu[1], int):
                muts.append([mu[0], ("obj", orig[mu[1]])] + mu[2:])
            else:
                muts.append(mu)
        for mu in muts:
            if mu[0] == "drop_obj":
                recs = [r for r in recs if r is not mu[1]]
            elif isinstance(mu[1], tuple):
                target = mu[1][1]
                if mu[0] == "retcode":
                    target["retcode"] = mu[2]
                else:
                    raise ValueError(f"unsupported original-index mutation {mu[0]}")
        spec = dict(spec, mutations=[])
    for mu in spec["mutations"]:
        op = mu[0]
        if op == "drop":
            del recs[mu[1]]
        elif op == "duplicate":
            recs.append(copy.deepcopy(recs[mu[1]]))
        elif op == "unexpected":
            recs.append(dict(copy.deepcopy(recs[mu[1]]), key=mu[2]))
        elif op == "set":
            recs[mu[1]][mu[2]] = mu[3]
        elif op == "del":
            del recs[mu[1]][mu[2]]
        elif op == "retcode":
            recs[mu[1]]["retcode"] = mu[2]
        elif op == "retcode_drop":
            del recs[mu[1]]["retcode"]
        elif op == "keep_none":
            recs = []
        elif op == "blank_lines":
            blank = True
    os.makedirs(d, exist_ok=True)
    n = spec["files"]
    if n == 0:
        return
    out = [[] for _ in range(n)]
    for r, rec in enumerate(recs):
        if blank and r % 50 == 0:
            out[r % n] += ["\n", "  \n"]
        out[r % n].append(json.dumps(rec) + "\n")
    for j in range(n):
        with open(os.path.join(d, f"s{j}.jsonl"), "w") as f:
            f.write("".join(out[j]))


def build_tree(files, troot):
    os.makedirs(troot, exist_ok=True)
    for spec in files:
        p = os.path.join(troot, spec["path"])
        if "records" in spec:
            write_records(p, spec["records"])
            continue
        if spec.get("remove"):
            os.remove(p)
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if "text" in spec:
            data = spec["text"].encode()
        elif "repo_copy" in spec:
            data = open(os.path.join(REPO, spec["repo_copy"]), "rb").read()
        elif "repo_text_replace" in spec:
            t = open(os.path.join(REPO, spec["repo_text_replace"]), encoding="utf-8").read()
            data = t.replace(spec["old"], spec["new"], spec["count"]).encode()
        else:
            raise ValueError(spec)
        with open(p, "wb") as f:
            f.write(data)


def resolve(step, troot):
    s = copy.deepcopy(step)
    for k in ("root", "bridge"):
        if isinstance(s.get(k), str):
            s[k] = troot if s[k] == "T" else REPO if s[k] == "R" else (
                os.path.join(troot, s[k][2:]) if s[k].startswith("T/") else os.path.join(REPO, s[k][2:]))
    if "records_dir" in s:
        d = os.path.join(troot, s.pop("records_dir")[2:])
        paths = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".jsonl")) if os.path.isdir(d) else []
        s["paths"] = paths + [os.path.join(troot, x[2:]) for x in s.pop("extra_paths", [])]
    if isinstance(s.get("parent_env"), str):
        s["parent_env"] = CONTRACT_DOC["parent_environments"][s["parent_env"]]
    return s


# ------------------------------------------------------------------------------------------------------------- python side
def classify(exc):
    msg = str(exc)
    if isinstance(exc, KeyError):
        return "KEY_ERROR", msg
    if isinstance(exc, FileNotFoundError):
        return "FILE_NOT_FOUND", msg
    if isinstance(exc, (json.JSONDecodeError, tomllib.TOMLDecodeError, UnicodeDecodeError)):
        return "DECODE_ERROR", msg
    if isinstance(exc, (TypeError, AttributeError)):
        return "TYPE_ERROR", msg
    if isinstance(exc, IndexError):
        return "INDEX_ERROR", msg
    return f"OTHER:{type(exc).__name__}", msg


def call(fn):
    try:
        return {"ok": json.loads(json.dumps(fn()))}
    except Exception as exc:  # noqa: BLE001
        k, m = classify(exc)
        return {"err": {"kind": k, "message": m}}


def projection(parent, extra=None):
    env = {k: parent[k] for k in PASS_THROUGH + THREAD_VARS if k in parent}
    env.update(extra or {})
    return env


def smoke_reference(out_path):
    wf = open(os.path.join(REPO, ".github/workflows/julia-smoke.yml"), encoding="utf-8").read()
    one_liner = re.search(r"NJOBS=\$\(python -c '(.*)'\)", wf).group(1)
    njobs = run([sys.executable, "-c", one_liner]).stdout.strip()
    line = re.search(r"(julia --project=hallthruster_bridge hallthruster_bridge/campaign/p5_n2_campaign\.jl \\\n\s*.*)", wf).group(1)
    line = line.replace("\\\n", " ").replace('"$RUNNER_TEMP/p5n2_smoke/smoke.jsonl"', out_path).replace('"$NJOBS"', njobs)
    env_block = re.search(r"env:\n\s+P5N2_SMOKE: \"(\d)\"", wf).group(1)
    return line.split(), {"P5N2_SMOKE": env_block}


def py_step(s):
    op = s["op"]
    if op == "build_manifests":
        return call(lambda: [[m["name"], json.dumps(m, indent=1)] for m in MM.build()])
    if op == "launch_spec":
        if s["kind"] == "campaign":
            argv = committed(s["manifest"])["commands"][s["shard"]].replace("<out>", s["out_dir"]).split()
            extra = None
        else:
            argv, extra = smoke_reference(s["out_path"])
        return {"ok": {"program": argv[0], "args": argv[1:], "cwd": REPO, "env": projection(s["parent_env"], extra),
                       "env_clear": True}}
    if op == "shard_partition":
        m = committed(s["manifest"])
        _, cands, cases = MM._inputs()
        jobs = [f"{cd}|{ch}|{cs}|{m['mode']}" for cd in cands for ch in m["chemistry"] for cs in cases]
        n = s["nshards"]
        return {"ok": [[i, sorted(k for ij, k in enumerate(jobs, 1) if (ij - 1) % n == i)] for i in range(n)]}
    if op == "check":
        def f():
            old = MM.BR
            try:
                if s.get("bridge"):
                    MM.BR = s["bridge"]
                return MM.check(committed(s["manifest"]), s["paths"])
            finally:
                MM.BR = old
        return call(f)
    if op == "pin":
        def f():
            root = s["root"]
            pin = tomllib.load(open(os.path.join(root, "hallthruster_bridge/PINNED.toml"), "rb"))
            man = tomllib.load(open(os.path.join(root, "hallthruster_bridge/Manifest.toml"), "rb"))
            commit, version, jv = pin["hallthruster"]["commit"], pin["hallthruster"]["version"], man["julia_version"]
            try:
                consistent = CI.check_hallthruster_pin(os.path.join(root, "hallthruster_bridge"))[0] == []
            except Exception:  # noqa: BLE001 - the check raising is a failed check
                consistent = False
            pinned = (commit, version, jv) == (BOUNDARY_PIN["commit"], BOUNDARY_PIN["version"],
                                               BOUNDARY_PIN["julia"].split()[0])
            return {"commit": commit, "version": version, "julia_version": jv, "manifest_consistent": consistent,
                    "pinned_constants": pinned, "verify_pin_ok": consistent and pinned}
        return call(f)
    raise ValueError(op)


def rust_step(s):
    r = run([BIN, "cases"], stdin=json.dumps({"repo": REPO, "step": s}), check=False)
    if r.returncode != 0:
        return {"err": {"kind": "HARNESS:RUST_EXIT", "message": r.stderr[-500:]}}, r.stdout
    return json.loads(r.stdout), r.stdout


# ------------------------------------------------------------------------------------------------------------- compare
def normalise(v, troot):
    if isinstance(v, str):
        return v.replace(troot, "<T>").replace(REPO, "<R>")
    if isinstance(v, list):
        return [normalise(x, troot) for x in v]
    if isinstance(v, dict):
        return {normalise(k, troot): normalise(x, troot) for k, x in v.items()}
    return v


def exact(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return set(a) == set(b) and all(exact(a[k], b[k]) for k in a)
    return a == b


def compare(p, r):
    if ("err" in p) != ("err" in r):
        return False, "ok/err differs"
    if "err" in p:
        if p["err"]["kind"] != r["err"]["kind"]:
            return False, f"kind {p['err']['kind']} != {r['err']['kind']}"
        if p["err"]["kind"] in MESSAGE_KINDS and p["err"]["message"] != r["err"]["message"]:
            return False, "message differs"
        return True, ""
    return (True, "") if exact(p["ok"], r["ok"]) else (False, "value differs")


# ------------------------------------------------------------------------------------------------------------- campaign
def random_cases(master):
    names = sorted(f[:-5] for f in os.listdir(os.path.join(REPO, "hallthruster_bridge/campaign/manifests")) if f.endswith(".json"))
    kinds = ["drop", "duplicate", "unexpected", "mode", "smoke", "lock", "commit", "retcode"]
    out = []
    for i in range(48):
        t = f"RC|{i}"
        name = names[U(master, f"{t}|m") % len(names)]
        m = committed(name)
        keys = list(m["expected_keys"])
        muts = []
        for j in range(U(master, f"{t}|k") % 4):
            kind = kinds[U(master, f"{t}|{j}|kind") % 8]
            idx = U(master, f"{t}|{j}|idx") % len(keys)
            if kind == "drop":
                muts.append(["drop", idx])
                del keys[idx]
            elif kind == "duplicate":
                muts.append(["duplicate", idx])
                keys.append(keys[idx])
            elif kind == "unexpected":
                muts.append(["unexpected", idx, keys[idx] + "|x"])
                keys.append(keys[idx] + "|x")
            elif kind == "mode":
                muts.append(["set", idx, "mode", "facility" if m["mode"] == "vacuum" else "vacuum"])
            elif kind == "smoke":
                muts.append(["set", idx, "smoke", True])
            elif kind == "lock":
                muts.append(["set", idx, "prereg_lock_sha256", "0" * 64])
            elif kind == "commit":
                muts.append(["set", idx, "hallthruster_commit", "1" * 40])
            else:
                muts.append(["retcode", idx, "failure"])
        out.append({"id": f"RC-{i:02d}", "group": "RANDOM", "note": name,
                    "files": [{"path": "rec", "records": {"manifest": name, "mutations": muts,
                                                          "files": 1 + U(master, f"{t}|files") % 4}}],
                    "steps": [{"op": "check", "manifest": name, "records_dir": "T/rec", "bridge": None}]})
    return out


INTERPRETATION_NOTES = [
    "IN-01: case CK-15 registers [drop, 0], [drop, 269], [retcode, 5, failure] for a 270-record set; applied in order "
    "the second index is out of range (IndexError). Its indices are applied to the unmutated set (records 0 and 269 "
    "dropped, record 5 'failure'), identically for both implementations (input construction only)"]


def run_case(case, work, timing):
    sides = {}
    for side in ("py", "rs"):
        troot = os.path.join(work, case["id"], side)
        files = case["files"]
        if case["id"] == "CK-15":
            files = [dict(f, records=dict(f["records"], original_indices=True)) if "records" in f else f for f in files]
        build_tree(files, troot)
        sides[side] = troot
    results = []
    for k, step in enumerate(case["steps"]):
        out, raw = {}, {}
        for side in ("py", "rs"):
            s = resolve(step, sides[side])
            t0 = time.perf_counter()
            if side == "py":
                o = py_step(s)
            else:
                o, raw[side] = rust_step(s)
            timing[side] += time.perf_counter() - t0
            out[side] = normalise(o, sides[side])
        agree, why = compare(out["py"], out["rs"])
        results.append({"step": k, "op": step["op"], "agree": agree, "reason": why, "python": out["py"],
                        "rust": out["rs"] if not agree else "== python"})
    return results


def tracked_manifest():
    files = run(["git", "ls-files", "-z"]).stdout.split("\0")
    return {f: sha_file(os.path.join(REPO, f)) for f in files if f and os.path.isfile(os.path.join(REPO, f))}


def forbidden_scan():
    hits = []
    for dp, _, fs in os.walk(os.path.join(REPO, "crates", "abep-julia-bridge")):
        for f in fs:
            if f.endswith(".rs"):
                text = open(os.path.join(dp, f), encoding="utf-8").read()
                hits += [f"{os.path.relpath(os.path.join(dp, f), REPO)}: {t}" for t in FORBIDDEN
                         if re.search(re.escape(t), text, re.IGNORECASE)]
    return hits


def invariants(per_case):
    by = {c["id"]: c for c in per_case}
    inv = {}
    # INV-02 from the Rust outcome of SP-01 (compared with the driver rule above)
    sp = by["SP-01"]
    ok = True
    for st, step in zip(sp["steps"], CONTRACT_DOC_CASES["SP-01"]["steps"]):
        exp = sorted(committed(step["manifest"])["expected_keys"])
        parts = st["python"]["ok"]
        allk = sorted(k for _, keys in parts for k in keys)
        sizes = [len(keys) for _, keys in parts]
        ok = ok and allk == exp and len(set(allk)) == len(allk) and max(sizes) - min(sizes) <= 1 and st["agree"]
    inv["INV-02_shard_partition"] = ok
    bad = []
    for c in per_case:
        if c["group"] == "LAUNCH" and c["id"].endswith("ENV-C"):
            for st in c["steps"]:
                env = st["python"]["ok"]["env"] if st["agree"] else st["rust"]["ok"]["env"]
                for k in env:
                    if k not in PASS_THROUGH + THREAD_VARS and not (k == "P5N2_SMOKE" and "smoke" in c["id"]):
                        bad.append(f"{c['id']}: {k}")
    inv["INV-04_allow_list_only"] = not bad
    return inv


def campaign(master):
    timing = {"py": 0.0, "rs": 0.0}
    work = tempfile.mkdtemp(prefix="bridgeparity_")
    per_case = []
    try:
        for case in CONTRACT_DOC["case_catalogue"] + random_cases(master):
            res = run_case(case, work, timing)
            per_case.append({"id": case["id"], "group": case["group"], "agree": all(r["agree"] for r in res), "steps": res})
            shutil.rmtree(os.path.join(work, case["id"]), ignore_errors=True)
        a = rust_step({"op": "build_manifests"})[1]
        b = rust_step({"op": "build_manifests"})[1]
        ls = CONTRACT_DOC_CASES["LS-facility_mandatory-ENV-B"]["steps"][0]
        c1 = rust_step(resolve(ls, work))[1]
        c2 = rust_step(resolve(ls, work))[1]
        det = a == b and c1 == c2
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return per_case, timing, det


CONTRACT_DOC_CASES = {c["id"]: c for c in CONTRACT_DOC["case_catalogue"]}


def committed_equality(per_case):
    st = {c["id"]: c for c in per_case}["MB-01"]["steps"][0]
    built = st["python"]["ok"] if st["agree"] else []
    d = os.path.join(REPO, "hallthruster_bridge/campaign/manifests")
    names = sorted(f for f in os.listdir(d) if f.endswith(".json"))
    same = sorted(f"{n}.json" for n, _ in built) == names and all(
        open(os.path.join(d, f"{n}.json"), "rb").read() == text.encode() for n, text in built)
    return same


def summary(per_case):
    by_group = {}
    for c in per_case:
        g = by_group.setdefault(c["group"], {"cases": 0, "agree": 0, "steps": 0, "python_err_steps": 0})
        g["cases"] += 1
        g["agree"] += c["agree"]
        g["steps"] += len(c["steps"])
        g["python_err_steps"] += sum("err" in s["python"] for s in c["steps"])
    dis = [{"case": c["id"], "step": s["step"], "op": s["op"], "reason": s["reason"], "python": s["python"],
            "rust": s["rust"]} for c in per_case for s in c["steps"] if not s["agree"]]
    return {"cases": len(per_case), "cases_agreeing": sum(c["agree"] for c in per_case),
            "steps_compared": sum(g["steps"] for g in by_group.values()), "disagreements": dis, "by_group": by_group}


def build_rust():
    run(["cargo", "build", "--locked", "-p", "abep-julia-bridge", "--bin", "abep-julia-bridge"])


def develop():
    build_rust()
    per_case, timing, det = campaign(CONTRACT_DOC["campaign_seeds"]["development_master_seed"])
    s = summary(per_case)
    print(json.dumps({k: v for k, v in s.items() if k != "disagreements"}, indent=1))
    for d in s["disagreements"][:30]:
        print(json.dumps(d)[:1500])
    print("INV-01", det, invariants(per_case), "committed_equal", committed_equality(per_case), timing)


def cargo_gate():
    out = {}
    r = run(["cargo", "fmt", "-p", "abep-julia-bridge", "-p", "abep-hall", "--", "--check"], check=False)
    out["fmt"] = {"command": "cargo fmt -p abep-julia-bridge -p abep-hall -- --check", "exit": r.returncode}
    r = run(["cargo", "clippy", "--workspace", "--all-targets", "--locked", "--", "-D", "warnings"], check=False)
    out["clippy"] = {"command": "cargo clippy --workspace --all-targets --locked -- -D warnings", "exit": r.returncode}
    r = run(["cargo", "test", "--workspace", "--locked"], check=False)
    counts = [tuple(int(x) for x in m) for m in re.findall(r"test result: \w+\. (\d+) passed; (\d+) failed; (\d+) ignored", r.stdout)]
    out["test"] = {"command": "cargo test --workspace --locked", "exit": r.returncode,
                   "passed": sum(c[0] for c in counts), "failed": sum(c[1] for c in counts),
                   "ignored": sum(c[2] for c in counts),
                   "ignored_note": "the ignored tests are PT-01 / PT-02 of the platform-test register"}
    out["pass"] = all(out[k]["exit"] == 0 for k in ("fmt", "clippy", "test"))
    return out


def write_md(rep):
    s = rep["summary"]
    lines = ["# C-JULIA-BRIDGE-LAUNCH parity report v1", "",
             f"Generated from `parity_report_v1.json` (contract `{rep['contract']['path']}`, sha256 `{rep['contract']['sha256']}`).",
             "", f"**Verdict: {rep['verdict']}. Admission: {rep['admission']}** (cargo gate "
                 f"{'pass' if rep['cargo_gate']['pass'] else 'FAIL'}: {rep['cargo_gate']['test']['passed']} tests passed, "
                 f"{rep['cargo_gate']['test']['ignored']} ignored = registered platform tests PT-01 / PT-02).", "",
             "## What was compared", "",
             "The Python reference (`scripts/make_p5_n2_launch_manifests.py` build / check, the committed manifest "
             "commands as the runner scripts execute them, `.github/workflows/julia-smoke.yml`, "
             "`scripts/ci_checks.py::check_hallthruster_pin`) and `abep-julia-bridge cases` on byte-identical trees. "
             "No Julia process was started; the run-record comparison is the registered platform test PT-02 (NOT_RUN "
             "here: no Julia in this environment).", "",
             f"* Commit: `{rep['python_commit']}`.",
             f"* Cases: {s['cases']}; steps compared: {s['steps_compared']}; cases agreeing: {s['cases_agreeing']}; "
             f"disagreements: {len(s['disagreements']) or 'none'}.", "", "## Decision rule", "", "| rule | holds |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in rep["decision"].items()]
    lines += ["", "## By group", "", "| group | cases | agree | steps | Python refusal steps |", "|---|---|---|---|---|"]
    lines += [f"| {g} | {v['cases']} | {v['agree']} | {v['steps']} | {v['python_err_steps']} |" for g, v in s["by_group"].items()]
    lines += ["", "## Platform tests", ""] + [f"* {p['id']}: {p['status']} ({p['why']})" for p in rep["platform_tests"]]
    lines += ["", "## Ledger update requested", ""] + [f"* {json.dumps(r, ensure_ascii=False)}" for r in rep["ledger_update_requested"]]
    with open(REPORT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")


def score():
    if os.path.exists(REPORT_JSON):
        sys.exit("parity_report_v1.json exists: the scoring seed is spent")
    refusals = [{"verdict": "REFUSED_REFERENCE_CHANGED", "file": f["path"]} for f in CONTRACT_DOC["reference_implementation"]["files"]
                if sha_file(os.path.join(REPO, f["path"])) != f["sha256_at_registration"]]
    refusals += [{"verdict": "INPUT_MISMATCH", "file": p} for p, h in CONTRACT_DOC["pinned_inputs_sha256"].items()
                 if sha_file(os.path.join(REPO, p)) != h]
    if refusals:
        sys.exit(json.dumps(refusals))
    if run(["git", "status", "--porcelain", "--untracked-files=no"]).stdout.strip():
        sys.exit("the scoring tree has uncommitted changes")
    commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    build_rust()
    before = tracked_manifest()
    seed = CONTRACT_DOC["campaign_seeds"]["scoring_master_seed"]
    t0 = time.time()
    per_case, timing, det = campaign(seed)
    wall = time.time() - t0
    after = tracked_manifest()
    gate = cargo_gate()
    s = summary(per_case)
    inv = invariants(per_case)
    decision = {"D1_every_step_agrees": not s["disagreements"], "D2_built_manifests_equal_committed": committed_equality(per_case),
                "INV-01_rust_deterministic": det, **inv, "INV-03_scoring_tree_unchanged": before == after,
                "INV-05_sidecar_field_set": "covered by cargo test sidecar_is_exactly_the_hall_physics_boundary_list "
                                            "(cargo gate)", "cargo_gate": gate["pass"]}
    verdict = "PARITY_PASS" if all(v is True or isinstance(v, str) for v in decision.values()) else "PARITY_FAIL"
    os.makedirs(REF_DIR, exist_ok=True)
    ref = os.path.join(REF_DIR, "python_outcomes_v1.json.gz")
    with open(ref, "wb") as f:
        f.write(gzip.compress((json.dumps({c["id"]: [st["python"] for st in c["steps"]] for c in per_case}, indent=1,
                                          sort_keys=True) + "\n").encode(), mtime=0))
    srcs = RUST_SOURCES + sorted(os.path.relpath(os.path.join(dp, f), REPO) for crate in ("abep-hall", "abep-julia-bridge")
                                 for dp, _, fs in os.walk(os.path.join(REPO, "crates", crate, "src")) for f in fs)
    rep = {
        "schema": "abep_rust_parity_report_v1", "id": "PARITY-REPORT-C-JULIA-BRIDGE-LAUNCH-V1",
        "contract": {"path": os.path.relpath(CONTRACT, REPO), "sha256": sha_file(CONTRACT), "id": CONTRACT_DOC["id"],
                     "registration_commit": run(["git", "log", "--format=%H", "-1", "--", os.path.relpath(CONTRACT, REPO)]).stdout.strip()},
        "harness": {"path": os.path.relpath(__file__, REPO), "sha256": sha_file(__file__)},
        "date": time.strftime("%Y-%m-%d", time.gmtime()), "python_commit": commit,
        "reference_files": [{"path": f["path"], "sha256_at_registration": f["sha256_at_registration"],
                             "sha256_at_scoring": sha_file(os.path.join(REPO, f["path"]))}
                            for f in CONTRACT_DOC["reference_implementation"]["files"]],
        "build_provenance": {"rust_commit": commit, "rustc": run(["rustc", "--version"]).stdout.strip(),
                             "cargo": run(["cargo", "--version"]).stdout.strip(),
                             "cargo_lock_sha256": sha_file(os.path.join(REPO, "Cargo.lock")),
                             "source_sha256": {p: sha_file(os.path.join(REPO, p)) for p in srcs}},
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "cpu_count": os.cpu_count(),
                        "requirements_lock_sha256": sha_file(os.path.join(REPO, "requirements-lock.txt")),
                        "thread_env": {k: os.environ.get(k, "unset") for k in THREAD_VARS}, "julia": "not installed"},
        "campaign_seeds": {"scoring_master_seed": seed, "random_check_sets": 48},
        "refusals": refusals, "interpretation_notes": INTERPRETATION_NOTES, "decision": decision, "summary": s,
        "classification_gate": {"forbidden_identifier_scan_crates_abep_julia_bridge": forbidden_scan() or "no hit"},
        "conservation": "NOT_APPLICABLE", "schema_parity": "manifest bytes (EXACT_BYTES) in MB-01",
        "performance": {"status": "reported, not a decision criterion", "python_seconds": timing["py"],
                        "rust_seconds": timing["rs"], "campaign_wall_seconds": round(wall, 1)},
        "platform_tests": [
            {"id": "PT-01", "status": "NOT_RUN", "why": "no Julia toolchain here; registered in "
                                                       "docs/rust_migration/test_register/platform_tests_v1.json"},
            {"id": "PT-02", "status": "NOT_RUN", "why": "run-record EXACT_BYTES comparison needs the pinned Julia; registered"}],
        "reference_outputs": {"path": os.path.relpath(ref, REPO), "sha256": sha_file(ref)},
        "verdict": verdict, "cargo_gate": gate, "admission": "ADMITTED" if verdict == "PARITY_PASS" else "NOT_ADMITTED",
        "admission_scope": "launch manifests, launch specifications (argv / allow-list environment / pinned thread settings), "
                           "structural gate, pin read and check, sidecar; the run-record comparison stays PT-02",
        "campaign_history": [
            {"execution": "development", "seed": CONTRACT_DOC["campaign_seeds"]["development_master_seed"],
             "note": "development executions before scoring; never a verdict"},
            {"execution": "scoring", "seed": seed, "commit": commit,
             "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "verdict": verdict}],
        "ledger_update_requested": [
            {"component": "C-SCRIPTS_MAKE_P5_N2_LAUNCH_MANIFESTS_PY",
             "status": "ADMITTED" if verdict == "PARITY_PASS" else "PREREG_PARITY",
             "authoritative_implementation": "rust: abep_julia_bridge::manifests / jobs / pin / sidecar / launch"
             if verdict == "PARITY_PASS" else "python",
             "contract": os.path.relpath(CONTRACT, REPO), "contract_sha256": sha_file(CONTRACT),
             "report": os.path.relpath(REPORT_JSON, REPO),
             "note": "run-record EXACT_BYTES (PT-02) pending the pinned Julia toolchain"},
            {"component": "C-SCRIPTS_IDENTIFY_P5_TRANSPORT_PY", "status": "FORMALLY_RETIRED_NOT_PORTED (proposed)",
             "note": "MIGRATE_OR_FORMALLY_RETIRE; P5-Xe identification CLOSED 2026-09-25; not ported (A9.29 sec. 14); a "
                     "reopening decision on new published evidence would need its own contract"}],
        "results": per_case,
    }
    with open(REPORT_JSON, "w") as f:
        f.write(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    write_md(rep)
    print(verdict, json.dumps(decision))


if __name__ == "__main__":
    {"develop": develop, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "develop"]()
