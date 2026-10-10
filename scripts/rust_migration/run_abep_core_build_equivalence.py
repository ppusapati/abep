"""Execute ADDENDUM-ABEP-CORE-BUILD-EQUIVALENCE-V1 (docs/rust_migration/contracts/C-ABEP_CORE_BUILD_EQUIVALENCE/).

Checks EQ-01 (abep_core sources), EQ-02 (toolchain), EQ-03 (feature set), runs S0 (`cargo test --release` in the
unmodified abep_core, target dir outside the tree), B0 (the recorded extension, through its Python functions), B1-B3
(workspace path-dependency builds of the crates/abep-intake case runner) and compares the per-case sha256 bitwise.
Writes result_v1.json and result_v1.md next to the addendum whatever the verdict.

    python3 scripts/rust_migration/run_abep_core_build_equivalence.py --extension-python <venv>/bin/python \
        --scratch <dir>
The B0 part re-invokes this file under the extension's interpreter with --b0 <out.json>.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import struct
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ADIR = os.path.join(ROOT, "docs", "rust_migration", "contracts", "C-ABEP_CORE_BUILD_EQUIVALENCE")
ADDENDUM = os.path.join(ADIR, "addendum_v1.json")
CARGO_BIN = "/root/.cargo/bin"


def sha256_file(p: str) -> str:
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_cases() -> dict:
    add = json.load(open(ADDENDUM))
    path = os.path.join(ROOT, add["case_set"]["path"])
    got = sha256_file(path)
    if got != add["case_set"]["sha256"]:
        raise SystemExit(f"case file sha256 {got} != registered {add['case_set']['sha256']}")
    return json.load(open(path))


# --- B0: the recorded extension -------------------------------------------------------------------------------------

def run_b0(out_path: str) -> None:
    import numpy as np
    import abep_core as ac

    so = [os.path.join(os.path.dirname(ac.__file__), f) for f in os.listdir(os.path.dirname(ac.__file__))
          if f.endswith(".so")]
    add = json.load(open(ADDENDUM))
    rec = add["admitted_basis"]["recorded_build_provenance"]
    so_sha = sha256_file(so[0]) if len(so) == 1 else None
    doc = {"extension_path": so[0] if so else None, "extension_sha256": so_sha,
           "extension_matches_recorded": so_sha == rec["extension_sha256"]}
    if not doc["extension_matches_recorded"]:
        json.dump(doc, open(out_path, "w"), indent=1)
        return
    cf = load_cases()
    sets = {k: np.array(v, dtype=np.float64) for k, v in cf["normal_sets"].items()}

    def normals(c):
        s = sets[c["normal_set"]]
        return np.ascontiguousarray(s[np.arange(c["n"]) % len(s)])

    def b(a, dt):
        return np.ascontiguousarray(a, dtype=dt).tobytes()

    digests = {}
    t0 = time.perf_counter()
    for c in cf["cases"]:
        f, n, k = c["f64"], c["n"], c["kernel"]
        if k in ("K1_entry", "K3_cll", "K4_trace"):
            ent_seed = c["seed"] if k == "K1_entry" else c["input_seed"]
            v_ent = ac.flux_weighted_entry(ent_seed, n, f["v_drift"], f["theta"], f["t"], f["m"])
        if k == "K1_entry":
            buf = b(v_ent, "<f8")
        elif k == "K2_diffuse":
            buf = b(ac.diffuse(c["seed"], normals(c), f["t_w"], f["m"]), "<f8")
        elif k == "K3_cll":
            out = ac.cll(c["seed"], v_ent, normals(c), f["t_w"], f["m"], f["alpha_n"], f["alpha_t"])
            buf = b(v_ent, "<f8") + b(out, "<f8")
        elif k == "K4_trace":
            col, v, hits, back, unres = ac.trace_channel(
                c["seed"], v_ent, f["r"], f["l"], f["alpha"], f["t_w"], f["m"], max_hits=c["max_hits"],
                scattering=c["scattering"], alpha_n=f["alpha_n"], alpha_t=f["alpha_t"],
                unresolved_tol=f["unresolved_tol"], max_hits_cap=c["max_hits_cap"])
            buf = (b(v_ent, "<f8") + b(col, np.uint8) + b(v, "<f8") + b(hits, "<i8") + b(back, np.uint8)
                   + struct.pack("<d", unres))
        elif k == "K5_clausing":
            buf = struct.pack("<d", ac.clausing_transmission(c["seed"], f["r"], f["l"], f["alpha"], f["t_w"], f["m"],
                                                              n=n))
        else:
            raise SystemExit(f"unknown kernel {k}")
        digests[c["id"]] = hashlib.sha256(buf).hexdigest()
    ids = [c["id"] for c in cf["cases"]]
    doc.update({"profile": "B0_recorded_extension", "n_cases": len(ids), "wall_s": time.perf_counter() - t0,
                "total_sha256": hashlib.sha256("\n".join(digests[i] for i in ids).encode()).hexdigest(),
                "cases": digests, "python": sys.version.split()[0], "numpy": np.__version__})
    json.dump(doc, open(out_path, "w"), indent=1)


# --- orchestration --------------------------------------------------------------------------------------------------

def env_with_cargo(extra: dict | None = None) -> dict:
    env = dict(os.environ)
    env["PATH"] = CARGO_BIN + os.pathsep + env.get("PATH", "")
    env.update(extra or {})
    return env


def run(cmd: list[str], env: dict, timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)


def cargo_example(label: str, target_dir: str, extra_args: list[str]) -> tuple[dict, dict]:
    env = env_with_cargo({"CARGO_TARGET_DIR": target_dir})
    build = ["cargo", "build", "--locked", "-p", "abep-intake", "--example", "abep_core_build_equivalence"] + extra_args
    t0 = time.perf_counter()
    rb = run(build, env)
    t_build = time.perf_counter() - t0
    if rb.returncode != 0:
        return {"error": rb.stderr[-4000:]}, {"command": " ".join(build)}
    runc = ["cargo", "run", "-q", "--locked", "-p", "abep-intake", "--example", "abep_core_build_equivalence"] + \
        extra_args + ["--", label]
    t0 = time.perf_counter()
    rr = run(runc, env)
    t_run = time.perf_counter() - t0
    if rr.returncode != 0:
        return {"error": rr.stderr[-4000:]}, {"command": " ".join(runc)}
    return json.loads(rr.stdout), {"build_command": " ".join(build), "run_command": " ".join(runc),
                                   "build_s": round(t_build, 2), "run_s": round(t_run, 2)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--b0", help="internal: run B0 under the extension interpreter and write JSON here")
    ap.add_argument("--extension-python", help="interpreter that imports the recorded abep_core extension")
    ap.add_argument("--scratch", help="directory for target dirs and intermediate files (outside the repository)")
    a = ap.parse_args()
    if a.b0:
        run_b0(a.b0)
        return 0
    if not (a.extension_python and a.scratch):
        ap.error("--extension-python and --scratch are required")
    os.makedirs(a.scratch, exist_ok=True)
    add = json.load(open(ADDENDUM))
    rec = add["admitted_basis"]["recorded_build_provenance"]
    started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    res: dict = {"schema": "abep_core_build_equivalence_result_v1", "addendum": {
        "path": os.path.relpath(ADDENDUM, ROOT), "sha256": sha256_file(ADDENDUM), "id": add["id"]},
        "executed_utc": started}

    # EQ-01
    src = {p: sha256_file(os.path.join(ROOT, p)) for p in rec["source_sha256"]}
    eq01 = {p: {"recorded": rec["source_sha256"][p], "actual": src[p], "equal": src[p] == rec["source_sha256"][p]}
            for p in src}
    res["EQ-01_sources"] = {"held": all(v["equal"] for v in eq01.values()), "files": eq01}
    # EQ-02
    env = env_with_cargo()
    rustc = run(["rustc", "--version"], env).stdout.strip()
    cargo = run(["cargo", "--version"], env).stdout.strip()
    res["EQ-02_toolchain"] = {"rustc": rustc, "cargo": cargo,
                              "held": rustc == rec["rustc"] and cargo == rec["cargo"]}
    if not res["EQ-01_sources"]["held"]:
        res["verdict"] = "REFUSED_SOURCE_CHANGED"
    elif not res["EQ-02_toolchain"]["held"]:
        res["verdict"] = "REFUSED_TOOLCHAIN"
    if "verdict" in res:
        return write(res)

    # EQ-03
    md = run(["cargo", "metadata", "--format-version", "1", "--locked"], env)
    meta = json.loads(md.stdout)
    pkgs = {p["id"]: p for p in meta["packages"]}
    names = sorted({p["name"] for p in meta["packages"]})
    core_nodes = [n for n in meta["resolve"]["nodes"] if pkgs[n["id"]]["name"] == "abep_core"]
    forbidden = sorted(set(names) & {"pyo3", "numpy", "pyo3-ffi", "maturin"})
    res["EQ-03_feature_set"] = {"abep_core_resolved_features": [n["features"] for n in core_nodes],
                                "forbidden_packages_in_graph": forbidden, "packages_in_graph": names,
                                "held": len(core_nodes) == 1 and core_nodes[0]["features"] == [] and not forbidden}

    # S0: in place as registered. In a nested git worktree (.claude/worktrees/...) Cargo's workspace search from
    # abep_core passes the worktree root (which excludes it) and reaches the enclosing checkout's Cargo.toml, so the
    # in-place command cannot run there; then (and only then) the same command runs on a sha256-verified byte-identical
    # copy of abep_core's sources outside the repository, and both attempts are recorded.
    s0_env = env_with_cargo({"CARGO_TARGET_DIR": os.path.join(a.scratch, "target_s0_abep_core")})
    s0_cmd = ["cargo", "test", "--release", "--locked", "--manifest-path", "abep_core/Cargo.toml"]
    s0 = run(s0_cmd, s0_env)
    attempts = [{"where": "in place (abep_core/)", "returncode": s0.returncode,
                 "stderr_tail": s0.stderr[-600:] if s0.returncode else ""}]
    if s0.returncode != 0 and "believes it's in a workspace when it's not" in s0.stderr:
        copy = os.path.join(a.scratch, "s0_abep_core_copy")
        os.makedirs(os.path.join(copy, "src"), exist_ok=True)
        copied = {}
        for p in rec["source_sha256"]:
            data = open(os.path.join(ROOT, p), "rb").read()
            dst = os.path.join(copy, os.path.relpath(p, "abep_core"))
            with open(dst, "wb") as f:
                f.write(data)
            copied[p] = sha256_file(dst) == rec["source_sha256"][p]
        s0 = run(["cargo", "test", "--release", "--locked", "--manifest-path", os.path.join(copy, "Cargo.toml")],
                 s0_env)
        attempts.append({"where": f"sha256-verified copy {copy}", "copy_matches_recorded_sha256": copied,
                         "returncode": s0.returncode})
        if not all(copied.values()):
            s0 = subprocess.CompletedProcess(s0.args, 1, s0.stdout, s0.stderr)
    summary = [ln for ln in (s0.stdout + s0.stderr).splitlines() if ln.startswith("test result:")]
    res["S0_standalone_cargo_test_release"] = {
        "command": "cargo test --release --locked --manifest-path abep_core/Cargo.toml (run from the repository root; "
                   "CARGO_TARGET_DIR outside the tree)",
        "attempts": attempts, "returncode": s0.returncode, "test_result_lines": summary, "held": s0.returncode == 0}
    res["abep_core_sources_after_S0"] = {p: sha256_file(os.path.join(ROOT, p)) == rec["source_sha256"][p] for p in src}

    # B0
    b0_path = os.path.join(a.scratch, "b0.json")
    t0 = time.perf_counter()
    r0 = subprocess.run([a.extension_python, os.path.abspath(__file__), "--b0", b0_path], cwd=ROOT,
                        capture_output=True, text=True, timeout=3600)
    if r0.returncode != 0:
        res["B0"] = {"error": r0.stderr[-4000:]}
        res["verdict"] = "NOT_RUN_EXTENSION_UNAVAILABLE"
        return write(res)
    b0 = json.load(open(b0_path))
    b0["driver_s"] = round(time.perf_counter() - t0, 2)
    if not b0.get("extension_matches_recorded"):
        res["B0"] = b0
        res["verdict"] = "NOT_RUN_EXTENSION_UNAVAILABLE"
        return write(res)

    # B1-B3
    builds = {
        "B1_workspace_release_standalone_profile": ["--release", "--config", "profile.release.lto=\"fat\"",
                                                    "--config", "profile.release.codegen-units=1",
                                                    "--config", "profile.release.opt-level=3"],
        "B2_workspace_debug": [],
        "B3_workspace_release": ["--release"],
    }
    outs = {}
    for label, extra in builds.items():
        out, info = cargo_example(label, os.path.join(a.scratch, "target_" + label.split("_")[0].lower()), extra)
        outs[label] = (out, info)

    ids = [c["id"] for c in load_cases()["cases"]]
    res["B0_reference_recorded_extension"] = {k: b0[k] for k in ("extension_path", "extension_sha256",
                                                                 "extension_matches_recorded", "n_cases",
                                                                 "total_sha256", "python", "numpy", "wall_s")}
    all_equal = True
    for label, (out, info) in outs.items():
        if "error" in out:
            res[label] = {"error": out["error"], **info, "equal_to_B0": False}
            all_equal = False
            continue
        diff = [i for i in ids if out["cases"].get(i) != b0["cases"][i]]
        res[label] = {**info, "debug_assertions": out["debug_assertions"], "n_cases": out["n_cases"],
                      "total_sha256": out["total_sha256"], "differing_cases": diff,
                      "equal_to_B0": not diff and out["n_cases"] == len(ids)}
        all_equal &= res[label]["equal_to_B0"]
    res["per_case_sha256_B0"] = b0["cases"]
    held = (res["EQ-03_feature_set"]["held"] and res["S0_standalone_cargo_test_release"]["held"]
            and all(res["abep_core_sources_after_S0"].values()))
    res["EQ-04_outputs"] = {"held": all_equal, "n_cases": len(ids)}
    res["verdict"] = "EQUIVALENT" if held and all_equal else "NOT_EQUIVALENT"
    return write(res)


def write(res: dict) -> int:
    res["environment"] = {
        "host": platform.platform(), "python": sys.version.split()[0],
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                                         text=True).stdout.strip()),
        "workspace_files_sha256": {p: sha256_file(os.path.join(ROOT, p)) for p in (
            "Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/abep-intake/Cargo.toml",
            "crates/abep-intake/src/build_equivalence.rs", "crates/abep-intake/examples/abep_core_build_equivalence.rs",
            "scripts/rust_migration/run_abep_core_build_equivalence.py")},
        "workspace_profile_release": "opt-level 3 (root Cargo.toml [profile.release]); Cargo defaults otherwise",
        "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "RAYON_NUM_THREADS")},
    }
    with open(os.path.join(ADIR, "result_v1.json"), "w") as f:
        json.dump(res, f, indent=1)
        f.write("\n")
    write_md(res)
    print(res["verdict"])
    return 0


def write_md(res: dict) -> None:
    L = [f"# abep_core build-equivalence addendum v1 — result: **{res['verdict']}**", "",
         f"Addendum `{res['addendum']['path']}` (sha256 `{res['addendum']['sha256']}`), executed {res['executed_utc']} "
         f"at `{res['environment']['git_head']}` (dirty: {res['environment']['git_dirty']}). Generated from "
         "`result_v1.json` by `scripts/rust_migration/run_abep_core_build_equivalence.py`.", "",
         "| check | held | detail |", "|---|---|---|"]
    if "EQ-01_sources" in res:
        L.append(f"| EQ-01 abep_core sources = parity_report_v2 | {res['EQ-01_sources']['held']} | 6 files |")
    if "EQ-02_toolchain" in res:
        t = res["EQ-02_toolchain"]
        L.append(f"| EQ-02 toolchain | {t['held']} | {t['rustc']}; {t['cargo']} |")
    if "EQ-03_feature_set" in res:
        t = res["EQ-03_feature_set"]
        L.append(f"| EQ-03 feature set | {t['held']} | abep_core features {t['abep_core_resolved_features']}; "
                 f"forbidden packages {t['forbidden_packages_in_graph']} |")
    if "S0_standalone_cargo_test_release" in res:
        t = res["S0_standalone_cargo_test_release"]
        L.append(f"| S0 `cargo test --release` in abep_core | {t['held']} | {'; '.join(t['test_result_lines'])} |")
    if "EQ-04_outputs" in res:
        L.append(f"| EQ-04 outputs bit-identical to B0 | {res['EQ-04_outputs']['held']} | "
                 f"{res['EQ-04_outputs']['n_cases']} cases |")
    L += ["", "| build | total sha256 | equal to B0 | differing cases |", "|---|---|---|---|"]
    if "B0_reference_recorded_extension" in res:
        b0 = res["B0_reference_recorded_extension"]
        L.append(f"| B0 recorded extension `{b0['extension_sha256'][:16]}…` | `{b0['total_sha256']}` | reference | - |")
    for k in ("B1_workspace_release_standalone_profile", "B2_workspace_debug", "B3_workspace_release"):
        if k in res:
            r = res[k]
            L.append(f"| {k} | `{r.get('total_sha256', 'error')}` | {r.get('equal_to_B0')} | "
                     f"{len(r.get('differing_cases', [])) if 'differing_cases' in r else 'error'} |")
    L += ["", "EQUIVALENT means the workspace path-dependency build of abep_core (rlib, no `python` feature) reproduces "
          "the admitted Kernel-1 binary bit for bit on the registered cases, so the parity_report_v2 ADMITTED status "
          "carries over to that consumption. It admits nothing else and is not physics evidence.", ""]
    with open(os.path.join(ADIR, "result_v1.md"), "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
