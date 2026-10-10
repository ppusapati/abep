"""Shared helpers of the SC-WP-05 parity harnesses (bus boundary, magnet power, RF matching): the Rust example
`power_eval`, the registered tolerance classes, provenance, reports and captured reference outputs.

The Python reference is imported read-only from this checkout; the repository is modified only in score mode, where
the contract directory receives its report and captured reference outputs.
"""
from __future__ import annotations

import datetime
import gzip
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parity_common as PC  # noqa: E402

ROOT = PC.ROOT
CARGO_ENV = dict(os.environ, PATH=f"/root/.cargo/bin:{os.environ.get('PATH', '')}", CARGO_INCREMENTAL="0",
                 CARGO_PROFILE_DEV_DEBUG="0")
PROVENANCE_SOURCES = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/abep-types/**",
                      "crates/abep-provenance/**", "crates/abep-subsystems/**"]
K_ULP, R_REL = 4, 1e-12


def decode(v):
    """Decode the registered markers {'$float': 'nan' | 'inf' | '-inf' | '-0.0'} recursively."""
    if isinstance(v, dict):
        if set(v) == {"$float"}:
            return float(v["$float"])
        return {k: decode(x) for k, x in v.items()}
    if isinstance(v, list):
        return [decode(x) for x in v]
    return v


def jsonable(v):
    """JSON shape of a Python result: tuples as lists, complex as [re, im]."""
    if isinstance(v, complex):
        return [v.real, v.imag]
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    return v


def py_result(fn, *a, **kw) -> dict:
    try:
        v = fn(*a, **kw)
    except Exception as e:  # noqa: BLE001 - every exception class is an observable
        tb = e.__traceback__
        frames = []
        while tb is not None:
            frames.append(tb.tb_frame.f_code.co_name)
            tb = tb.tb_next
        return {"outcome": "RAISED", "class": type(e).__name__, "message": str(e), "frames": frames}
    return {"outcome": "RETURNED", "value": json.loads(json.dumps(jsonable(v)))}


def cargo_build() -> Path:
    subprocess.run(["cargo", "build", "--release", "--locked", "-p", "abep-subsystems", "--example", "power_eval",
                    "--example", "power_cons_l1"], cwd=ROOT, check=True, env=CARGO_ENV, capture_output=True)
    return ROOT / "target" / "release" / "examples"


def rust_eval(bindir: Path, calls: list, work: Path, tag: str) -> tuple[list, bytes]:
    p = work / f"calls_{tag}.json"
    p.write_text(json.dumps(calls, ensure_ascii=True), encoding="utf-8")
    r = subprocess.run([str(bindir / "power_eval"), str(p)], capture_output=True, check=True, cwd=ROOT)
    return json.loads(r.stdout), r.stdout


def ulp_ok(r: float, p: float) -> tuple[bool, float]:
    if math.isnan(p) or math.isnan(r):
        return (math.isnan(p) and math.isnan(r)), 0.0
    if math.isinf(p) or math.isinf(r):
        return r == p, 0.0
    d = abs(r - p)
    u = math.ulp(p) if p != 0 else math.ulp(0.0)
    return (d <= K_ULP * u or d <= R_REL * max(1.0, abs(p))), (d / u if u else 0.0)


def tree_diff(p, r, path="$", stats=None):
    """Differences between a Python and a Rust JSON value under the registered tolerance classes."""
    stats = stats if stats is not None else {"max_ulp": 0.0, "floats": 0}
    if isinstance(p, bool) or isinstance(r, bool):
        return ([] if (type(p) is type(r) and p == r) else [f"{path}: {p!r} != {r!r}"]), stats
    if isinstance(p, float) and isinstance(r, float):
        ok, u = ulp_ok(r, p)
        stats["floats"] += 1
        stats["max_ulp"] = max(stats["max_ulp"], u)
        return ([] if ok else [f"{path}: float {p!r} != {r!r}"]), stats
    if type(p) is not type(r):
        return [f"{path}: type {type(p).__name__} != {type(r).__name__} ({p!r:.80} / {r!r:.80})"], stats
    if isinstance(p, dict):
        if list(p) != list(r):
            return [f"{path}: keys {list(p)} != {list(r)}"], stats
        out = []
        for k in p:
            out += tree_diff(p[k], r[k], f"{path}.{k}", stats)[0]
        return out, stats
    if isinstance(p, list):
        if len(p) != len(r):
            return [f"{path}: length {len(p)} != {len(r)}"], stats
        out = []
        for i, (a, b) in enumerate(zip(p, r)):
            out += tree_diff(a, b, f"{path}[{i}]", stats)[0]
        return out, stats
    return ([] if p == r else [f"{path}: {p!r:.120} != {r!r:.120}"]), stats


def compare(py: dict, rs: dict, message_classes: set[str]) -> tuple[list[str], dict]:
    stats = {"max_ulp": 0.0, "floats": 0}
    if py["outcome"] != rs["outcome"]:
        return [f"outcome {py['outcome']} != {rs['outcome']} (py {py.get('class')}: {py.get('message')!r:.300}; "
                f"rust {rs.get('class')}: {rs.get('message')!r:.300}; rust value {str(rs.get('value'))[:200]})"], stats
    if py["outcome"] == "RETURNED":
        return tree_diff(py["value"], rs["value"], "$", stats)
    out = []
    if py["class"] != rs["class"]:
        out.append(f"class {py['class']} != {rs['class']} (py {py['message']!r:.300}; rust {rs['message']!r:.300})")
    elif py["class"] in message_classes and py["message"] != rs["message"]:
        out.append(f"message differs: py {py['message']!r} | rust {rs['message']!r}")
    return out, stats


def environment() -> dict:
    env = PC.environment()
    env["requirements_lock_sha256"] = PC.sha_file(ROOT / "requirements-lock.txt")
    return env


def git_state() -> dict:
    head = PC.git("rev-parse", "HEAD")
    dirty = PC.git("status", "--porcelain") != ""
    return {"git_head": head, "git_dirty": dirty}


def build_provenance() -> dict:
    src = PC.source_sha256(PROVENANCE_SOURCES)
    digest = hashlib.sha256(json.dumps(src, sort_keys=True).encode()).hexdigest()
    rustc = subprocess.run(["/root/.cargo/bin/rustc", "--version"], capture_output=True, text=True).stdout.strip()
    cargo = subprocess.run(["/root/.cargo/bin/cargo", "--version"], capture_output=True, text=True).stdout.strip()
    return {"rustc": rustc, "cargo": cargo,
            "profile": "release (cargo build --release --locked -p abep-subsystems --example power_eval --example "
                       "power_cons_l1)",
            "cargo_lock_sha256": PC.sha_file(ROOT / "Cargo.lock"), "source_sha256": src,
            "source_sha256_digest": digest}


def check_reference(contract: dict) -> tuple[list, list]:
    changed = [f["path"] for f in contract["reference_implementation"]["files"]
               if PC.sha_file(ROOT / f["path"]) != f["sha256_at_registration"]]
    pinned_bad = [p for p, h in contract.get("pinned_inputs_sha256", {}).items() if PC.sha_file(ROOT / p) != h]
    return changed, pinned_bad


def write_reference_outputs(cdir: Path, files: dict, python_commit: str, git_head: str) -> dict:
    """gzip-compressed canonical JSON (mtime 0) of the captured inputs and Python outputs, and their manifest."""
    out = cdir / "reference_outputs"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"captured_at_python_commit": python_commit, "scoring_git_head": git_head,
                "format": "gzip (mtime 0) of json.dumps(obj, indent=None, ensure_ascii=True, allow_nan=True)",
                "files": {}}
    for name, obj in files.items():
        raw = json.dumps(obj, ensure_ascii=True).encode("utf-8")
        data = gzip.compress(raw, mtime=0)
        (out / name).write_bytes(data)
        manifest["files"][name] = {"sha256": PC.sha_bytes(data), "uncompressed_sha256": PC.sha_bytes(raw)}
    mp = out / "MANIFEST.json"
    mp.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return {"path": str(out.relative_to(ROOT)), "manifest_sha256": PC.sha_file(mp), "files": manifest["files"]}


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_report(cdir: Path, report: dict, md: str) -> None:
    PC.write_report(cdir / "parity_report_v1.json", report, md)


def md_report(r: dict, title: str) -> str:
    lines = [f"# {title}", "",
             f"Generated from `parity_report_v1.json`. Verdict: **{r['verdict']}** (parity {r['parity']}).", "",
             f"* Contract: `{r['contract']['path']}` (sha256 `{r['contract']['sha256']}`)",
             f"* Python reference commit `{r['python_commit']}`; reference files unchanged at scoring: "
             f"{r['reference_unchanged_at_scoring']}",
             f"* Rust commit `{r['rust_commit']}` (tree dirty: {r['scoring_execution']['git_dirty']}), "
             f"{r['build_provenance']['rustc']}",
             f"* Scoring seed {r['scoring_execution']['master_seed']}; harness `{r['harness']['path']}` sha256 "
             f"`{r['harness']['sha256']}`", "", "## Calls", "", "| item | value |", "|---|---|"]
    for k, v in r["per_test"]["counts"].items():
        lines.append(f"| {k} | {v} |")
    lines += ["", f"Mismatches: {r['per_test']['mismatches']}. Largest float distance: "
                  f"{r['per_test']['max_ulp_distance']:.3g} ulp over {r['per_test']['floats_compared']} floats.", "",
              "## Invariants", "", "| id | pass | detail |", "|---|---|---|"]
    for k, v in r["invariants"].items():
        lines.append(f"| {k} | {v['pass']} | {v['detail']} |")
    lines += ["", "## Conservation", "", "| id | pass | detail |", "|---|---|---|"]
    for k, v in r["conservation"].items():
        lines.append(f"| {k} | {v['pass']} | {v['detail']} |")
    lines += ["", "## Domain and error parity", "", "| class | Python RAISED calls |", "|---|---|"]
    for k, v in r["domain_and_error"]["python_raised_by_class"].items():
        lines.append(f"| {k} | {v} |")
    if r["domain_and_error"].get("divergences_observed"):
        lines += ["", "Registered divergences observed:", ""]
        for k, v in r["domain_and_error"]["divergences_observed"].items():
            lines.append(f"* {k}: {v}")
    lines += ["", "## Performance (reported, not a decision criterion)", "", "| workload | Python s | Rust s | note |",
              "|---|---|---|---|"]
    for k, v in r["performance"].items():
        lines.append(f"| {k} | {v['python_s']:.4g} | {v['rust_s']:.4g} | {v.get('note', '')} |")
    if r.get("findings"):
        lines += ["", "## Findings", ""]
        for f in r["findings"]:
            lines.append(f"* {f}")
    lines += ["", "## Ledger update requested", "", "```json", json.dumps(r["ledger_update_requested"], indent=1),
              "```", "", "## What this is not", ""]
    for w in r["what_this_is_not"]:
        lines.append(f"* {w}")
    if r["per_test"]["failures"]:
        lines += ["", "## Failures (first 40)", ""]
        for f in r["per_test"]["failures"][:40]:
            lines.append(f"* `{json.dumps(f, ensure_ascii=False)[:600]}`")
    return "\n".join(lines) + "\n"


def platform_line() -> str:
    return f"{platform.system()} {platform.release()} {platform.machine()}"


# ============================================================================================== generic campaign
def run_campaign(*, cid: str, contract_path: Path, harness: Path, mode: str, work: Path, build_calls, py_call,
                 message_classes: set[str], invariants_fn, conservation_fn, perf_specs, ledger_request: list,
                 findings: list | None = None) -> tuple[dict, dict | None]:
    """Registered + randomized calls: Python reference vs `power_eval`, invariants, conservation, performance; in
    score mode the report and the captured reference outputs are written next to the contract."""
    import re as _re
    import shutil as _shutil
    import time as _time
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes)
    seeds = contract["campaign_seeds"]
    seed = seeds["scoring_master_seed"] if mode == "score" else seeds["development_master_seed"]
    t0 = _time.time()
    if work.exists():
        _shutil.rmtree(work)
    work.mkdir(parents=True)
    changed, pinned_bad = check_reference(contract)
    if changed:
        return {"verdict": "REFUSED_REFERENCE_CHANGED", "changed": changed}, None
    gs = git_state()
    bindir = cargo_build()
    calls = build_calls(contract, seed)
    rows = [{"case": c, "fn": f, "args": a, "py": py_call(f, a)} for c, f, a in calls]
    rcalls = [{"fn": r["fn"], "args": r["args"]} for r in rows]
    rs, rbytes = rust_eval(bindir, rcalls, work, "a")
    _, rbytes2 = rust_eval(bindir, rcalls, work, "b")
    failures, max_ulp, floats, raised = [], 0.0, 0, {}
    for r, rr in zip(rows, rs):
        exp = {k: v for k, v in r["py"].items() if k != "frames"}
        d, st = compare(exp, rr, message_classes)
        max_ulp, floats = max(max_ulp, st["max_ulp"]), floats + st["floats"]
        r["rs"] = rr
        if d:
            failures.append({"case": r["case"], "fn": r["fn"], "diff": d[:5]})
        if r["py"]["outcome"] == "RAISED":
            raised[r["py"]["class"]] = raised.get(r["py"]["class"], 0) + 1
    invariants = {"determinism": {"pass": rbytes == rbytes2,
                                  "detail": "Rust outputs of two separate processes byte-identical"}}
    invariants.update(invariants_fn(rows))
    conservation = conservation_fn(rows)
    perf = {}
    for pid, fn, a, n in perf_specs(rows):
        from parity_common import timed
        py_s = timed(lambda: [py_call(fn, a) for _ in range(n)])
        tt = []
        for _ in range(3):
            res, _b = rust_eval(bindir, [{"fn": fn, "args": a, "repeat": n}], work, "perf")
            tt.append(res[0]["elapsed_s"])
        rust_s = sorted(tt)[1]
        perf[pid] = {"python_s": py_s, "rust_s": rust_s, "speedup": py_s / rust_s if rust_s else None,
                     "note": f"{n} evaluations; Rust timed inside power_eval (no process start)"}
    ok = not failures and all(v["pass"] for v in invariants.values()) and all(v["pass"] for v in
                                                                             conservation.values()) and not pinned_bad
    verdict = "ADMITTED" if ok else ("INPUT_MISMATCH" if pinned_bad else "NOT_ADMITTED")
    rnd = _re.compile(r"^R\d+-")
    counts = {"calls_total": len(rows), "registered_calls": sum(1 for r in rows if not rnd.match(r["case"])),
              "randomized_calls": sum(1 for r in rows if rnd.match(r["case"])),
              "python_RETURNED": sum(r["py"]["outcome"] == "RETURNED" for r in rows),
              "python_RAISED": sum(r["py"]["outcome"] == "RAISED" for r in rows)}
    for fn in sorted({r["fn"] for r in rows}):
        counts[f"calls {fn}"] = sum(r["fn"] == fn for r in rows)
    summary = {"verdict": verdict, "mismatches": len(failures), "counts": counts, "max_ulp": max_ulp,
               "invariants": {k: v["pass"] for k, v in invariants.items()},
               "conservation": {k: v["pass"] for k, v in conservation.items()}, "wall_s": round(_time.time() - t0, 1),
               "failures": failures[:30]}
    if mode != "score":
        return summary, None
    cdir = contract_path.parent
    if verdict != "ADMITTED":
        for x in ledger_request:
            x["status"] = "NOT_ADMITTED"
    cap = write_reference_outputs(cdir, {
        "calls_v1.json.gz": [{"case": r["case"], "fn": r["fn"], "args": r["args"]} for r in rows],
        "python_results_v1.json.gz": [{"case": r["case"], "fn": r["fn"], "result": {k: v for k, v in r["py"].items()
                                                                                     if k != "frames"}}
                                      for r in rows],
    }, contract["reference_implementation"]["python_commit"], gs["git_head"])
    bp = build_provenance()
    rep_path = cdir / "parity_report_v1.json"
    prev = json.loads(rep_path.read_text())["campaign_history"] if rep_path.exists() else []
    hist = prev + [{"utc": utc(), "git_head": gs["git_head"], "git_dirty": gs["git_dirty"], "master_seed": seed,
                    "contract_sha256": PC.sha_bytes(contract_bytes), "source_sha256_digest": bp["source_sha256_digest"],
                    "verdict": verdict, "wall_s": summary["wall_s"]}]
    report = {
        "report_schema": "abep_rust_parity_report_v3_1", "id": "PARITY-REPORT-" + cid + "-V1", "lane": "SC-WP-05",
        "contract": {"path": str(contract_path.relative_to(ROOT)), "sha256": PC.sha_bytes(contract_bytes),
                     "id": contract["id"]},
        "verdict": verdict, "parity": "PARITY_PASS" if verdict == "ADMITTED" else "PARITY_FAIL",
        "verdict_rule": contract["decision_rules"]["verdict"],
        "python_commit": contract["reference_implementation"]["python_commit"],
        "reference_sha256": {f["path"]: f["sha256_at_registration"] for f in
                             contract["reference_implementation"]["files"]},
        "reference_unchanged_at_scoring": True, "pinned_inputs_verified": not pinned_bad,
        "rust_commit": gs["git_head"], "build_provenance": bp, "environment": environment(),
        "harness": {"path": str(harness.relative_to(ROOT)), "sha256": PC.sha_file(harness),
                    "common": {"scripts/rust_migration/parity_power_common.py": PC.sha_file(
                        ROOT / "scripts/rust_migration/parity_power_common.py"),
                        "scripts/rust_migration/parity_common.py": PC.sha_file(
                        ROOT / "scripts/rust_migration/parity_common.py")}},
        "scoring_execution": {"utc": utc(), "git_dirty": gs["git_dirty"], "master_seed": seed,
                              "rust_calls_sha256": PC.sha_bytes(json.dumps(rcalls, ensure_ascii=True).encode())},
        "per_test": {"counts": counts, "mismatches": len(failures), "failures": failures,
                     "max_ulp_distance": max_ulp, "floats_compared": floats,
                     "tolerance": "EXACT_VALUE structure / strings / ints; ULP_BOUNDED floats (4 ulp or 1e-12 "
                                  "relative)"},
        "aggregates": "NOT_APPLICABLE", "invariants": invariants, "conservation": conservation,
        "domain_and_error": {"python_raised_by_class": raised, "divergences_observed": {},
                             "message_classes_scored": sorted(message_classes)},
        "schema": {"pass": not failures, "detail": "field names, order and types compared on every returned value"},
        "performance": perf, "captured_reference_outputs": cap, "campaign_history": hist,
        "development_runs": f"development seed {seeds['development_master_seed']} runs were not scored or reported "
                            "(contract development_rule)",
        "findings": findings or [], "ledger_update_requested": ledger_request,
        "meaning_of_ADMITTED": contract["decision_rules"]["meaning_of_ADMITTED"],
        "what_this_is_not": contract["what_this_is_not"],
    }
    write_report(cdir, report, md_report(report, "Parity report " + cid + " v1"))
    return summary, report


def loguniform(rng, lo, hi):
    return 10 ** rng.uniform(math.log10(lo), math.log10(hi))
