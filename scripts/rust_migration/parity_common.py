"""Shared helpers of the Rust parity harnesses (A9.29 lane A2): case trees, the Rust CLI, provenance, reports.

The Python reference is imported read-only from this checkout; case trees live in a scratch directory and the
repository is never modified.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_TOP = {".git", "target", "config"}


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    return sha_bytes(Path(p).read_bytes())


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def link_tree(src: Path, dst: Path, edits: set[str], rel: str = "") -> None:
    """Symlink farm of src at dst; every path in ``edits`` (and its parents) is a real directory / real copy."""
    dst.mkdir(parents=True, exist_ok=True)
    for e in sorted(src.iterdir()):
        r = f"{rel}/{e.name}" if rel else e.name
        if not rel and e.name in SKIP_TOP:
            continue
        touched = any(x == r or x.startswith(r + "/") for x in edits)
        if not touched:
            os.symlink(e, dst / e.name)
        elif e.is_dir() and not e.is_symlink():
            link_tree(e, dst / e.name, edits, r)
        else:
            shutil.copy2(e, dst / e.name)


def make_repo(dst: Path, edits: set[str]) -> Path:
    """A case repository: symlinks to this checkout, real copies along ``edits``, a real copy of config/."""
    link_tree(ROOT, dst, edits)
    shutil.copytree(ROOT / "config", dst / "config")
    for x in edits:
        (dst / x).parent.mkdir(parents=True, exist_ok=True)
    return dst


def cargo_build() -> Path:
    env = dict(os.environ, PATH=f"/root/.cargo/bin:{os.environ.get('PATH', '')}")
    subprocess.run(["cargo", "build", "--release", "--locked", "-p", "abep-config"], cwd=ROOT, check=True, env=env,
                   capture_output=True)
    return ROOT / "target" / "release" / "abep-config"


def rust_eval(binary: Path, calls: list, work: Path, tag: str) -> tuple[list, bytes]:
    p = work / f"calls_{tag}.json"
    p.write_text(json.dumps(calls, ensure_ascii=True), encoding="utf-8")
    r = subprocess.run([str(binary), "eval", str(p)], capture_output=True, check=True)
    return json.loads(r.stdout), r.stdout


def py_result(fn, *a, **kw) -> dict:
    try:
        v = fn(*a, **kw)
    except Exception as e:  # noqa: BLE001 - every exception class is an observable
        return {"outcome": "RAISED", "class": type(e).__name__, "message": str(e)}
    return {"outcome": "RETURNED", "value": v}


def canon(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def compare(py: dict, rs: dict, message_classes: set[str]) -> list[str]:
    """Differences between one Python and one Rust result (empty = parity)."""
    if py["outcome"] != rs["outcome"]:
        return [f"outcome {py['outcome']} != {rs['outcome']} (py {py.get('class')}: {py.get('message')!r}; "
                f"rust {rs.get('class')}: {rs.get('message')!r})"]
    if py["outcome"] == "RETURNED":
        a, b = canon(py["value"]), canon(rs["value"])
        return [] if a == b else [f"value differs: py {a[:300]} | rust {b[:300]}"]
    out = []
    if py["class"] != rs["class"]:
        out.append(f"class {py['class']} != {rs['class']} (py message {py['message']!r}; rust {rs['message']!r})")
    elif py["class"] in message_classes and py["message"] != rs["message"]:
        out.append(f"message differs: py {py['message']!r} | rust {rs['message']!r}")
    return out


def environment() -> dict:
    import numpy
    rustc = subprocess.run(["/root/.cargo/bin/rustc", "--version"], capture_output=True, text=True).stdout.strip()
    cargo = subprocess.run(["/root/.cargo/bin/cargo", "--version"], capture_output=True, text=True).stdout.strip()
    return {"python": platform.python_version(), "numpy": numpy.__version__, "rustc": rustc, "cargo": cargo,
            "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
            "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")}}


def source_sha256(paths: list[str]) -> dict:
    out = {}
    for pat in paths:
        if pat.endswith("/**"):
            base = ROOT / pat[:-3]
            for p in sorted(base.rglob("*")):
                if p.is_file():
                    out[p.relative_to(ROOT).as_posix()] = sha_file(p)
        else:
            out[pat] = sha_file(ROOT / pat)
    return out


def timed(fn, repeats: int = 3) -> float:
    ts = []
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t)
    return sorted(ts)[len(ts) // 2]


def write_report(path_json: Path, report: dict, md: str) -> None:
    path_json.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    path_json.with_suffix(".md").write_text(md, encoding="utf-8")
