#!/usr/bin/env python3
"""Parity harness of C-HALL-MAP-ENSEMBLE-REGISTRY v1 (parity_prereg_v1.json in this directory).

Builds every registered case tree twice (one per implementation) with the contract's case language, executes each
step with the unmodified Python reference (abep_sim.hall_map / hall_ensemble / hallmap_registry,
abep_sim.design.architecture_optimizer.hall_response_status) and with the Rust binary abep-hall-cases, and compares
the outcomes under the registered identity and tolerance rules. The random maps of random_map_procedure are drawn
from the given master seed.

  python3 -B parity_harness.py develop     development seed; never a verdict; summary to stdout
  python3 -B parity_harness.py score       the single scoring execution: parity_report_v1.json + .md + reference_outputs/

Migration tooling only. The repository tree is never written except the report files of the scoring run.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CONTRACT = os.path.join(HERE, "parity_prereg_v1.json")
REPORT_JSON = os.path.join(HERE, "parity_report_v1.json")
REPORT_MD = os.path.join(HERE, "parity_report_v1.md")
REF_DIR = os.path.join(HERE, "reference_outputs")
BIN = os.path.join(REPO, "target", "debug", "abep-hall-cases")
MESSAGE_KINDS = {"VALUE_ERROR", "REGISTRY_ERROR", "KEY_ERROR", "FILE_NOT_FOUND", "SCIPY_VALUE_ERROR"}
FLAGS = ("converged", "sustained", "chemistry_trustworthy", "wall_life_trustworthy")
RUST_SOURCES = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/abep-types/src/lib.rs",
                "crates/abep-provenance/src/lib.rs", "crates/abep-hall/Cargo.toml"]
FORBIDDEN = ["LaB6Cathode", "lab6_xe", "cathode_life", "XE_CATHODE", "hall_1stage", "mw_air", "rf_cathode",
             "CONTROL_FALLBACK", "keeper", "heater", "hollow", "cathode"]

sys.path.insert(0, REPO)
from abep_sim import hall_ensemble as he  # noqa: E402
from abep_sim import hall_map as hm  # noqa: E402
from abep_sim import hallmap_registry as reg  # noqa: E402
from abep_sim.design import architecture_optimizer as ao  # noqa: E402


# ------------------------------------------------------------------------------------------------------------- utilities
def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: str) -> str:
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


def pointer_parts(ptr: str):
    return [p.replace("~1", "/").replace("~0", "~") for p in ptr.split("/")[1:]]


def ptr_get(doc, ptr):
    node = doc
    for p in pointer_parts(ptr):
        node = node[int(p)] if isinstance(node, list) else node[p]
    return node


def ptr_set(doc, ptr, value):
    parts = pointer_parts(ptr)
    parent = ptr_get(doc, "/" + "/".join(x.replace("~", "~0").replace("/", "~1") for x in parts[:-1])) if parts[:-1] else doc
    last = parts[-1]
    if isinstance(parent, list):
        if last == "-":
            parent.append(value)
        else:
            parent[int(last)] = value
    else:
        parent[last] = value


def ptr_del(doc, ptr):
    parts = pointer_parts(ptr)
    parent = ptr_get(doc, "/" + "/".join(x.replace("~", "~0").replace("/", "~1") for x in parts[:-1])) if parts[:-1] else doc
    if isinstance(parent, list):
        del parent[int(parts[-1])]
    else:
        del parent[parts[-1]]


def U(master, tag) -> int:
    return int.from_bytes(hashlib.sha256(f"{master}|{tag}".encode()).digest()[:8], "big")


def u01(master, tag) -> float:
    return (U(master, tag) >> 11) * 2.0 ** -53


# ------------------------------------------------------------------------------------------------------------- tree build
def nested(shape, fn, idx=()):
    if not shape:
        return fn(idx)
    return [nested(shape[1:], fn, idx + (i,)) for i in range(shape[0])]


def flatten(v):
    if isinstance(v, list):
        out = []
        for x in v:
            out += flatten(x)
        return out
    return [v]


def build_hallmap(spec):
    """The contract's hallmap file spec: (document text, document)."""
    meta = {k: "synthetic" for k in hm.REQUIRED_META}
    meta.update(schema="hall_map_schema_v1", pinned=f'commit = "{hm.pinned_commit()}"', ensemble_member_id="synthetic",
                ion_wall_losses=True, evidence_status="SYNTHETIC_TEST_ONLY_NOT_EVIDENCE")
    meta.update(spec.get("meta", {}))
    for k in spec.get("drop_meta", []):
        meta.pop(k, None)
    axes = spec["axes"]
    fields = {}
    shape = [len(a) for a in axes.values()] if all(isinstance(a, list) for a in axes.values()) else []
    fs = spec.get("fill_scale")
    for f in hm.REQUIRED_FIELDS:
        if "fields_raw" in spec:
            fields[f] = copy.deepcopy(spec["fields_raw"]["@all"])
        elif spec.get("scalar"):
            fields[f] = 1 if f in FLAGS else 0.02
        elif f in FLAGS:
            fields[f] = nested(shape, lambda idx: 1)
        elif fs == "@ramp":
            fields[f] = nested(shape, lambda idx: 0.5 + sum(i * 2 ** k for k, i in enumerate(idx)))
        elif fs is not None:
            fields[f] = copy.deepcopy(fs)
        else:
            fields[f] = nested(shape, lambda idx: 0.02)
        if spec.get("flat"):
            fields[f] = flatten(fields[f])
    for k, v in spec.get("fields", {}).items():
        fields[k] = v
    for k, v in spec.get("extra_fields", {}).items():
        fields[k] = v
    for k in spec.get("drop_fields", []):
        fields.pop(k, None)
    doc = {"meta": meta, "axes": axes, "fields": fields}
    if "replace_meta" in spec:
        doc["meta"] = spec["replace_meta"]
    for k in spec.get("drop_top", []):
        doc.pop(k, None)
    text = json.dumps(doc)
    if "text_prefix_axes" in spec:
        text = text.replace('"axes": {', '"axes": {' + spec["text_prefix_axes"], 1)
    return text, doc


def resolve_value(v, troot):
    if isinstance(v, str):
        if v.startswith("@sha256:"):
            return sha_file(os.path.join(troot, v[8:]))
        if v.startswith("@gzc:"):
            if not v.endswith(".gz"):        # interpretation note IN-01: an uncompressed file's content is its bytes
                return sha_file(os.path.join(troot, v[5:]))
            with gzip.open(os.path.join(troot, v[5:]), "rb") as g:
                return sha_bytes(g.read())
        if v.startswith("@canon:"):
            path, ptr = v[7:].split("#", 1)
            return hashlib.sha256(json.dumps(ptr_get(load(os.path.join(troot, path)), ptr), sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
        if v.startswith("@abs:T/"):
            return os.path.join(troot, v[7:])
        return v
    if isinstance(v, list):
        return [resolve_value(x, troot) for x in v]
    if isinstance(v, dict):
        return {k: resolve_value(x, troot) for k, x in v.items()}
    return v


def build_tree(files, troot, label_check):
    os.makedirs(troot, exist_ok=True)
    for spec in files:
        p = os.path.join(troot, spec["path"])
        if spec.get("remove"):
            os.remove(p)
            continue
        if spec.get("dir"):
            os.makedirs(p, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(p) or troot, exist_ok=True)
        if "json" in spec:
            data = json.dumps(resolve_value(spec["json"], troot)).encode()
        elif "text" in spec:
            data = spec["text"].encode()
        elif "gzip_text" in spec:
            data = gzip.compress(spec["gzip_text"].encode(), mtime=0)
        elif "repo_copy" in spec:
            data = open(os.path.join(REPO, spec["repo_copy"]), "rb").read()
        elif "repo_text_replace" in spec:
            t = open(os.path.join(REPO, spec["repo_text_replace"]), encoding="utf-8").read()
            data = t.replace(spec["old"], spec["new"], spec["count"]).encode()
        elif "repo_json" in spec:
            doc = load(os.path.join(REPO, spec["repo_json"]))
            for ptr in spec.get("del", []):
                ptr_del(doc, ptr)
            for ptr, val in spec.get("set", []):
                ptr_set(doc, ptr, resolve_value(copy.deepcopy(val), troot))
            data = json.dumps(doc).encode()
        elif "hallmap" in spec:
            text, doc = build_hallmap(spec["hallmap"])
            meta = doc.get("meta")
            label_check.append(isinstance(meta, dict) and meta.get("evidence_status") == "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE"
                               or "meta" in spec["hallmap"].get("drop_top", []) or "replace_meta" in spec["hallmap"])
            data = text.encode()
        else:
            raise ValueError(f"unknown file spec {spec}")
        with open(p, "wb") as f:
            f.write(data)


PATH_KEYS = {"path", "bridge_dir", "root", "registry", "repo", "file", "raw", "loaded"}


def resolve_step(step, troot, prior):
    def walk(v, key=None):
        if isinstance(v, dict):
            return {k: walk(x, k) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x, key) for x in v]
        if isinstance(v, str):
            if v.startswith("@step:"):
                o = prior[int(v[6:])]
                return o.get("ok") if isinstance(o, dict) else None
            if v.startswith(("@sha256:", "@gzc:", "@canon:", "@abs:")):
                return resolve_value(v, troot)
            if key in PATH_KEYS:
                if v == "T":
                    return troot
                if v == "R":
                    return REPO
                if v.startswith("T/"):
                    return os.path.join(troot, v[2:])
                if v.startswith("R/"):
                    return os.path.join(REPO, v[2:])
        return v
    return walk(step)


# ------------------------------------------------------------------------------------------------------------- python side
NUMPY_PATTERNS = [("RAGGED", r"setting an array element with a sequence.*"), ("RESHAPE", r"cannot reshape array of size .*"),
                  ("CONVERT", r"could not convert string to float: .*"), ("TRUTH", r"The truth value of an array .*"),
                  ("TRUTH", r"The truth value of an empty array .*")]


def classify(exc):
    frames = traceback.extract_tb(exc.__traceback__)
    inner = frames[-1].filename if frames else ""
    msg = str(exc)
    if isinstance(exc, reg.RegistryError):
        return "REGISTRY_ERROR", msg
    if isinstance(exc, KeyError):
        return "KEY_ERROR", msg
    if isinstance(exc, FileNotFoundError):
        return "FILE_NOT_FOUND", msg
    if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)):
        return "DECODE_ERROR", msg
    if isinstance(exc, (OSError, EOFError)) or type(exc).__name__ == "error":
        return "OS_ERROR", msg
    if isinstance(exc, (TypeError, AttributeError)):
        return "TYPE_ERROR", msg
    if isinstance(exc, IndexError):
        return "INDEX_ERROR", msg
    if isinstance(exc, ValueError):
        if "scipy" in inner.replace("\\", "/").split("/"):
            return "SCIPY_VALUE_ERROR", msg
        for sub, pat in NUMPY_PATTERNS:
            if re.fullmatch(pat, msg, re.DOTALL):
                return f"NUMPY_VALUE_ERROR:{sub}", msg
        if "abep_sim" in inner.replace("\\", "/"):
            return "VALUE_ERROR", msg
    return f"OTHER:{type(exc).__name__}", msg


def py_call(fn):
    try:
        return {"ok": json.loads(json.dumps(fn()))}
    except Exception as exc:  # noqa: BLE001 - every exception is an outcome
        kind, msg = classify(exc)
        return {"err": {"kind": kind, "message": msg}}


def override(e):
    if e is None:
        return None
    for k in ("raw", "file"):
        if k in e:
            return load(e[k])
    return None


def qfloat(v):
    return float(v) if isinstance(v, str) else v


def py_step(step):
    op = step["op"]
    a = step.get
    if op == "required_fields":
        return py_call(lambda: {"fields": list(hm.REQUIRED_FIELDS), "meta": list(hm.REQUIRED_META)})
    if op == "missing_fields":
        return py_call(lambda: hm.missing_fields(a("record")))
    if op == "pinned_commit":
        return py_call(lambda: hm.pinned_commit(a("bridge_dir")))
    if op == "load_schema_v2":
        return py_call(lambda: reg.load_hall_map_schema_v2(a("root")))
    if op == "hallmap":
        def f():
            m = hm.HallMap(a("path"), a("bridge_dir"), ensemble=override(a("ensemble")))
            qs = []
            for q in a("queries"):
                qq = {k: qfloat(v) for k, v in q.items()}
                qs.append(py_call(lambda qq=qq: [[k, v] for k, v in m(**qq).items()]))
            return {"names": list(m.names), "shape": [len(m.axes[k]) for k in m.names], "queries": qs}
        return py_call(f)
    if op == "load_ensemble":
        def f():
            e = he.load_ensemble(a("path")) if a("path") is not None else he.load_ensemble()
            return {"member_ids": sorted(he.member_ids(e)), "screening_ids": sorted(he.screening_ids(e))}
        return py_call(f)
    if op == "require_admitted":
        def f():
            e = a("ensemble")
            doc = None if e is None else (he.load_ensemble(e["loaded"]) if "loaded" in e else override(e))
            return he.require_admitted(a("member_id"), doc)
        return py_call(f)
    if op == "hall_response_status":
        from pathlib import Path
        return py_call(lambda: ao.hall_response_status(Path(a("repo"))))
    if op == "register":
        return py_call(lambda: reg.register(a("registry"), a("root"), ensemble=override(a("ensemble")), **a("kw")))
    if op == "withdraw":
        return py_call(lambda: reg.withdraw(a("registry"), a("root"), record_sha256=a("record_sha256"), reason=a("reason"),
                                            decision_file=a("decision_file"), registered_by=a("registered_by"),
                                            registered_utc=a("registered_utc"), ensemble=override(a("ensemble"))))
    if op == "verify":
        return py_call(lambda: reg.verify(a("registry"), a("root"), ensemble=override(a("ensemble"))))
    if op == "lookup_map_meta":
        return py_call(lambda: reg.lookup_map_meta(a("registry"), a("root"), a("map_meta_sha256"),
                                                   ensemble=override(a("ensemble"))))
    if op == "build_registration":
        return py_call(lambda: reg.build_registration(a("root"), seq=step.get("seq", 1),
                                                      prev_record_sha256=step.get("prev_record_sha256"), **a("kw")))
    if op == "validate_record":
        return py_call(lambda: reg.validate_record(a("record")))
    if op == "read_records":
        return py_call(lambda: [[n, s, r] for n, s, r in reg.read_records(a("registry"))])
    if op == "canonical_json_sha256":
        return py_call(lambda: reg.canonical_json_sha256(a("value")))
    if op == "sha256_canonical_jsonl":
        return py_call(lambda: reg.sha256_canonical_jsonl(a("path")))
    raise ValueError(f"unknown op {op}")


def rust_step(step):
    r = run([BIN], stdin=json.dumps({"repo": REPO, "step": step}), check=False)
    if r.returncode != 0:
        return {"err": {"kind": "HARNESS:RUST_EXIT", "message": r.stderr[-500:]}}, r.stdout
    return json.loads(r.stdout), r.stdout


# ------------------------------------------------------------------------------------------------------------- mutations
def registry_files(registry):
    d = os.path.join(registry, "records")
    recs = None
    if os.path.isdir(d):
        recs = []
        for n in sorted(os.listdir(d)):
            p = os.path.join(d, n)
            mode = os.stat(p).st_mode
            recs.append({"name": n, "sha256": sha_file(p) if os.path.isfile(p) else None,
                         "readonly": not (mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))})
    tmp = sorted(n for n in os.listdir(registry) if n.startswith(".tmp_")) if os.path.isdir(registry) else []
    return {"ok": {"records": recs, "tmp": tmp}}


def first_record(registry):
    d = os.path.join(registry, "records")
    return os.path.join(d, sorted(os.listdir(d))[0])


def mutate(step):
    op = step["op"]
    if op == "write":
        p = step["path"]
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if "text" in step:
            data = step["text"].encode()
        else:
            t = open(os.path.join(REPO, step["repo_text_replace"]), encoding="utf-8").read()
            data = t.replace(step["old"], step["new"], step["count"]).encode()
        if os.path.exists(p):
            os.chmod(p, 0o644)
        with open(p, "wb") as f:
            f.write(data)
    elif op == "tamper_first_record":
        p = first_record(step["registry"])
        os.chmod(p, 0o644)
        rec = load(p)
        for ptr, val in step["set"]:
            ptr_set(rec, ptr, val)
        with open(p, "w") as f:
            f.write(json.dumps(rec, sort_keys=True, indent=1) + "\n")
    elif op == "remove_first_record":
        os.remove(first_record(step["registry"]))
    return {"ok": None}


def record_from(step, troot):
    rf = step.get("record_from")
    if rf is None:
        return step
    registry = os.path.join(troot, "registry")
    d = os.path.join(registry, "records")
    names = [n for n in sorted(os.listdir(d)) if n.startswith(f"{rf['registry_seq']:06d}_")] if os.path.isdir(d) else []
    if not names:
        return None
    rec = load(os.path.join(d, names[0]))
    for ptr in step.get("del", []):
        ptr_del(rec, ptr)
    for ptr, val in step.get("set", []):
        ptr_set(rec, ptr, val)
    return {"op": "validate_record", "record": rec}


# ------------------------------------------------------------------------------------------------------------- comparison
def normalise(v, troot):
    if isinstance(v, str):
        return v.replace(troot, "<T>").replace(REPO, "<R>")
    if isinstance(v, list):
        return [normalise(x, troot) for x in v]
    if isinstance(v, dict):
        return {normalise(k, troot): normalise(x, troot) for k, x in v.items()}
    return v


def same_float(a, b):
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return struct_bits(a) == struct_bits(b)


def struct_bits(x):
    import struct
    return struct.pack("<d", x)


def ulp_ok(r, p):
    if math.isnan(p) or math.isnan(r):
        return math.isnan(p) and math.isnan(r)
    if math.isinf(p) or math.isinf(r):
        return r == p
    return abs(r - p) <= 4 * math.ulp(p) or abs(r - p) <= 1e-12 * max(1.0, abs(p))


def exact(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        return same_float(a, b)
    if isinstance(a, list):
        return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return set(a) == set(b) and all(exact(a[k], b[k]) for k in a)
    return a == b


class Stats:
    def __init__(self):
        self.floats = 0
        self.bitwise = 0


def compare_outcome(op, p, r, stats):
    """(agree, reason)."""
    if ("err" in p) != ("err" in r):
        return False, "ok/err differs"
    if "err" in p:
        if p["err"]["kind"] != r["err"]["kind"]:
            return False, f"kind {p['err']['kind']} != {r['err']['kind']}"
        if p["err"]["kind"] in MESSAGE_KINDS and p["err"]["message"] != r["err"]["message"]:
            return False, "message differs"
        return True, ""
    pv, rv = p["ok"], r["ok"]
    if op == "hallmap":
        if not (exact(pv["names"], rv["names"]) and exact(pv["shape"], rv["shape"]) and len(pv["queries"]) == len(rv["queries"])):
            return False, "names / shape / query count differ"
        for i, (pq, rq) in enumerate(zip(pv["queries"], rv["queries"])):
            if ("err" in pq) != ("err" in rq):
                return False, f"query {i}: ok/err differs"
            if "err" in pq:
                ok, why = compare_outcome("query", pq, rq, stats)
                if not ok:
                    return False, f"query {i}: {why}"
                continue
            if [k for k, _ in pq["ok"]] != [k for k, _ in rq["ok"]]:
                return False, f"query {i}: keys differ"
            for (k, a), (_, b) in zip(pq["ok"], rq["ok"]):
                if isinstance(a, float) and isinstance(b, float) and not isinstance(a, bool):
                    stats.floats += 1
                    stats.bitwise += same_float(a, b)
                    if not ulp_ok(b, a):
                        return False, f"query {i}: {k} {b!r} vs {a!r}"
                elif not exact(a, b):
                    return False, f"query {i}: {k} {b!r} vs {a!r}"
        return True, ""
    if not exact(pv, rv):
        return False, "value differs"
    if op == "verify" and list(pv["records"]) != list(rv["records"]):
        return False, "verify records order differs"
    return True, ""


# ------------------------------------------------------------------------------------------------------------- random maps
def random_cases(master):
    out = []
    syn = None
    for c in CONTRACT_DOC["case_catalogue"]:
        if c["id"] == "M-01":
            syn = c["files"][0]
    for i in range(240):
        t = f"RM|{i}"
        d = 1 + U(master, f"{t}|dims") % 4
        axes = {}
        for k in range(d):
            n = 1 + U(master, f"{t}|n|{k}") % 4
            xs = [-100 + 200 * u01(master, f"{t}|x0|{k}")]
            for j in range(1, n):
                xs.append(xs[-1] + 0.001 + 50 * u01(master, f"{t}|dx|{k}|{j}"))
            axes[f"x{k}"] = xs
        shape = [len(v) for v in axes.values()]
        size = math.prod(shape)
        fields = {}
        for f in hm.REQUIRED_FIELDS:
            vals = []
            for p in range(size):
                u = u01(master, f"{t}|f|{f}|{p}")
                if f in ("converged", "chemistry_trustworthy", "wall_life_trustworthy"):
                    vals.append(1 if u < 0.85 else 0)
                elif f == "sustained":
                    vals.append(1 if u < 0.8 else (0.9995 if u < 0.9 else 0.5))
                else:
                    vals.append((u - 0.5) * 10 ** (U(master, f"{t}|e|{f}|{p}") % 7 - 3))
            arr = vals
            for n in reversed(shape[1:]):
                arr = [arr[j:j + n] for j in range(0, len(arr), n)]
            fields[f] = arr
        queries = []
        for j in range(6):
            q = {}
            for k, (name, xs) in enumerate(axes.items()):
                mode = U(master, f"{t}|q|{j}|{k}") % 4
                lo, hi = xs[0], xs[-1]
                q[name] = [lo + (hi - lo) * u01(master, f"{t}|v|{j}|{k}"), xs[U(master, f"{t}|node|{j}|{k}") % len(xs)],
                           lo, hi][mode]
            queries.append(q)
        spec = {"axes": axes, "fields_random": fields, "meta": {"ion_wall_losses": u01(master, f"{t}|iwl") < 0.7}}
        out.append({"id": f"RM-{i:03d}", "group": "RANDOM", "files": [syn, {"path": "m.json", "hallmap_random": spec}],
                    "steps": [{"op": "hallmap", "path": "T/m.json", "bridge_dir": None,
                               "ensemble": {"file": "T/ens_syn.json"}, "queries": queries}]})
    return out


def build_tree_any(files, troot, label_check):
    for spec in files:
        if "hallmap_random" not in spec:
            build_tree([spec], troot, label_check)
            continue
        _, doc = build_hallmap({"axes": spec["hallmap_random"]["axes"], "meta": spec["hallmap_random"]["meta"]})
        doc["fields"] = spec["hallmap_random"]["fields_random"]
        label_check.append(doc["meta"].get("evidence_status") == "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE")
        p = os.path.join(troot, spec["path"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(json.dumps(doc))


# ------------------------------------------------------------------------------------------------------------- campaign
MUTATIONS = {"write", "tamper_first_record", "remove_first_record"}


def run_case(case, work, stats, label_check, timing):
    sides = {}
    for side in ("py", "rs"):
        troot = os.path.join(work, case["id"], side)
        build_tree_any(case["files"], troot, label_check if side == "py" else [])
        sides[side] = troot
    results, prior, written = [], {"py": [], "rs": []}, {"py": [], "rs": []}
    for k, step in enumerate(case["steps"]):
        out = {}
        for side in ("py", "rs"):
            troot = sides[side]
            rs = resolve_step(step, troot, prior[side])
            if rs["op"] in MUTATIONS:
                o = mutate(rs)
            elif rs["op"] == "registry_files":
                o = registry_files(rs["registry"])
            else:
                if rs["op"] == "validate_record" and "record_from" in rs:
                    rs = record_from(rs, troot)
                if rs is None:
                    o = {"err": {"kind": "HARNESS:NO_RECORD", "message": "record_from found no record"}}
                else:
                    t0 = time.perf_counter()
                    o = py_step(rs) if side == "py" else rust_step(rs)[0]
                    timing[side] += time.perf_counter() - t0
            prior[side].append(o)
            out[side] = normalise(o, troot)
        if step["op"] in MUTATIONS:
            results.append({"step": k, "op": step["op"], "agree": True, "compared": False})
            continue
        if step["op"] in ("register", "withdraw"):
            for side in ("py", "rs"):
                sha = prior[side][-1].get("ok")
                if isinstance(sha, str):
                    written[side].append(sha)
        agree, why = compare_outcome(step["op"], out["py"], out["rs"], stats)
        results.append({"step": k, "op": step["op"], "agree": agree, "reason": why, "python": out["py"],
                        "rust": out["rs"] if not agree else "== python (within tolerance)"})
    inv2 = True
    if not any(st["op"] in ("tamper_first_record", "remove_first_record") for st in case["steps"]):
        for side, troot in sides.items():
            regd = os.path.join(troot, "registry")
            rf = registry_files(regd)["ok"] if os.path.isdir(regd) else {"records": [], "tmp": []}
            inv2 = inv2 and not rf["tmp"]
            by_prefix = {r["name"][7:23]: r for r in rf["records"] or []}
            for sha in written[side]:
                r = by_prefix.get(sha[:16])
                inv2 = inv2 and r is not None and r["readonly"] and r["sha256"] == sha
    return results, sides, inv2


def tracked_manifest():
    files = run(["git", "ls-files", "-z"]).stdout.split("\0")
    return {f: sha_file(os.path.join(REPO, f)) for f in files if f and os.path.isfile(os.path.join(REPO, f))}


def forbidden_scan():
    hits = []
    for dp, _, fs in os.walk(os.path.join(REPO, "crates", "abep-hall")):
        for f in fs:
            if f.endswith(".rs"):
                text = open(os.path.join(dp, f), encoding="utf-8").read()
                for tok in FORBIDDEN:
                    if re.search(re.escape(tok), text, re.IGNORECASE):
                        hits.append(f"{os.path.relpath(os.path.join(dp, f), REPO)}: {tok}")
    return hits


def campaign(master, keep_outcomes):
    stats, label_check, timing = Stats(), [], {"py": 0.0, "rs": 0.0}
    work = tempfile.mkdtemp(prefix="hallparity_")
    cases = CONTRACT_DOC["case_catalogue"] + random_cases(master)
    per_case, python_outcomes = [], {}
    try:
        for case in cases:
            res, sides, inv2 = run_case(case, work, stats, label_check, timing)
            if keep_outcomes:
                python_outcomes[case["id"]] = [r.get("python") for r in res]
            if case["group"] == "RANDOM":
                res = [{k: v for k, v in r.items() if k not in ("python", "rust")} if r["agree"] else r for r in res]
            per_case.append({"id": case["id"], "group": case["group"], "agree": all(r["agree"] for r in res),
                             "inv02": inv2, "steps": res})
            shutil.rmtree(os.path.join(work, case["id"]), ignore_errors=True)
        # INV-01: Rust determinism on the random maps
        det = True
        rdir = os.path.join(work, "det")
        for case in cases[-240:]:
            troot = os.path.join(rdir, case["id"])
            build_tree_any(case["files"], troot, [])
            step = resolve_step(case["steps"][0], troot, [])
            a = rust_step(step)[1]
            b = rust_step(step)[1]
            det = det and a == b
            shutil.rmtree(troot, ignore_errors=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return per_case, stats, label_check, timing, det, python_outcomes


def governed_state(per_case):
    by = {c["id"]: c for c in per_case}
    e01 = by["E-01"]["steps"][0]["python"]
    e70 = by["E-70"]["steps"][0]["python"]
    e63 = by["E-63"]["steps"]
    return {
        "E-01_member_ids_empty": e01.get("ok", {}).get("member_ids") == [] and by["E-01"]["agree"],
        "E-70_credible_set_EMPTY": e70.get("ok", {}).get("credible_set") == "EMPTY" and by["E-70"]["agree"],
        "E-63_nine_screening_refused": len(e63) == 9 and by["E-63"]["agree"] and all(
            s["python"].get("err", {}).get("kind") == "VALUE_ERROR" and "is a SCREENING candidate" in s["python"]["err"]["message"]
            for s in e63)}


CONTRACT_DOC = load(CONTRACT)


def build_rust():
    run(["cargo", "build", "--locked", "-p", "abep-hall", "--bin", "abep-hall-cases"])


def check_inputs():
    refusals = []
    for f in CONTRACT_DOC["reference_implementation"]["files"]:
        if sha_file(os.path.join(REPO, f["path"])) != f["sha256_at_registration"]:
            refusals.append({"verdict": "REFUSED_REFERENCE_CHANGED", "file": f["path"]})
    for p, h in CONTRACT_DOC["pinned_inputs_sha256"].items():
        if sha_file(os.path.join(REPO, p)) != h:
            refusals.append({"verdict": "INPUT_MISMATCH", "file": p})
    return refusals


def summary(per_case, stats):
    by_group = {}
    for c in per_case:
        g = by_group.setdefault(c["group"], {"cases": 0, "agree": 0, "steps": 0, "python_err_steps": 0})
        g["cases"] += 1
        g["agree"] += c["agree"]
        for s in c["steps"]:
            if s.get("compared", True):
                g["steps"] += 1
                g["python_err_steps"] += isinstance(s.get("python"), dict) and "err" in s["python"]
    dis = [{"case": c["id"], "step": s["step"], "op": s["op"], "reason": s["reason"], "python": s.get("python"),
            "rust": s.get("rust")} for c in per_case for s in c["steps"] if not s["agree"]]
    return {"cases": len(per_case), "cases_agreeing": sum(c["agree"] for c in per_case),
            "steps_compared": sum(g["steps"] for g in by_group.values()), "disagreements": dis, "by_group": by_group,
            "interpolated_floats": stats.floats, "bitwise_identical_floats": stats.bitwise}


def develop():
    build_rust()
    seed = CONTRACT_DOC["campaign_seeds"]["development_master_seed"]
    per_case, stats, labels, timing, det, _ = campaign(seed, False)
    s = summary(per_case, stats)
    print(json.dumps({k: v for k, v in s.items() if k != "disagreements"}, indent=1))
    for d in s["disagreements"][:40]:
        print(json.dumps(d)[:1500])
    print("INV-01", det, "INV-02", all(c["inv02"] for c in per_case), "INV-05", all(labels), "timing", timing)
    print("governed", governed_state(per_case))


def cargo_gate():
    out = {}
    r = run(["cargo", "fmt", "-p", "abep-hall", "--", "--check"], check=False)
    out["fmt"] = {"command": "cargo fmt -p abep-hall -- --check", "exit": r.returncode}
    r = run(["cargo", "clippy", "--workspace", "--all-targets", "--locked", "--", "-D", "warnings"], check=False)
    out["clippy"] = {"command": "cargo clippy --workspace --all-targets --locked -- -D warnings", "exit": r.returncode}
    r = run(["cargo", "test", "--workspace", "--locked"], check=False)
    counts = [tuple(int(x) for x in m) for m in re.findall(r"test result: \w+\. (\d+) passed; (\d+) failed; (\d+) ignored",
                                                            r.stdout)]
    out["test"] = {"command": "cargo test --workspace --locked", "exit": r.returncode,
                   "passed": sum(c[0] for c in counts), "failed": sum(c[1] for c in counts),
                   "ignored": sum(c[2] for c in counts),
                   "ignored_note": "ignored tests are the registered platform tests of "
                                   "docs/rust_migration/test_register/platform_tests_v1.json (Rust-era test rule)"}
    out["pass"] = out["fmt"]["exit"] == 0 and out["clippy"]["exit"] == 0 and out["test"]["exit"] == 0
    return out


def write_md(rep):
    s = rep["summary"]
    lines = [f"# C-HALL-MAP-ENSEMBLE-REGISTRY parity report v1", "",
             f"Generated from `parity_report_v1.json` (contract `{rep['contract']['path']}`, sha256 "
             f"`{rep['contract']['sha256']}`).", "",
             f"**Verdict: {rep['verdict']}. Admission: {rep['admission']}** (cargo fmt / clippy / test gate: "
             f"{'pass' if rep['cargo_gate']['pass'] else 'FAIL'}, {rep['cargo_gate']['test']['passed']} tests passed, "
             f"{rep['cargo_gate']['test']['ignored']} ignored = registered platform tests).", "",
             "## What was compared", "",
             "The unmodified Python reference (`abep_sim/hall_map.py`, `hall_ensemble.py`, `hallmap_registry.py`, "
             "`design/architecture_optimizer.py::hall_response_status`) and the Rust crate `abep-hall` "
             "(binary `abep-hall-cases`) executed every registered step on byte-identical case trees.", "",
             f"* Commit: `{rep['python_commit']}` (Python reference and Rust).",
             f"* Cases: {s['cases']} ({len(CONTRACT_DOC['case_catalogue'])} registered + 240 random maps, scoring seed "
             f"{rep['campaign_seeds']['scoring_master_seed']}); steps compared: {s['steps_compared']}; cases agreeing: "
             f"{s['cases_agreeing']}.",
             f"* Interpolated floats compared (ULP_BOUNDED): {s['interpolated_floats']}; bitwise identical: "
             f"{s['bitwise_identical_floats']} (information only).",
             f"* Disagreements: {len(s['disagreements']) or 'none'}.", "", "## Decision rule", "", "| rule | holds |",
             "|---|---|"]
    for k, v in rep["decision"].items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## By group", "", "| group | cases | agree | steps | Python refusal steps |", "|---|---|---|---|---|"]
    for g, v in s["by_group"].items():
        lines.append(f"| {g} | {v['cases']} | {v['agree']} | {v['steps']} | {v['python_err_steps']} |")
    lines += ["", "## Governed state (credible transport set EMPTY)", ""]
    for k, v in rep["governed_state"].items():
        lines.append(f"* {k}: {v}")
    lines += ["", "## Ledger update requested", ""]
    for r in rep["ledger_update_requested"]:
        lines.append(f"* {json.dumps(r, ensure_ascii=False)}")
    lines += ["", "## Performance (reported, not a decision criterion)", "",
              f"* Python step time {rep['performance']['python_seconds']:.2f} s, Rust step time (process per step) "
              f"{rep['performance']['rust_seconds']:.2f} s.", ""]
    with open(REPORT_MD, "w") as f:
        f.write("\n".join(lines))


def score():
    if os.path.exists(REPORT_JSON):
        sys.exit("parity_report_v1.json exists: the scoring seed is spent")
    refusals = check_inputs()
    commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    if run(["git", "status", "--porcelain", "--untracked-files=no"]).stdout.strip():
        sys.exit("the scoring tree has uncommitted changes")
    if refusals:
        sys.exit(json.dumps(refusals))
    build_rust()
    before = tracked_manifest()
    seed = CONTRACT_DOC["campaign_seeds"]["scoring_master_seed"]
    t0 = time.time()
    per_case, stats, labels, timing, det, py_out = campaign(seed, True)
    wall = time.time() - t0
    after = tracked_manifest()
    gate = cargo_gate()
    s = summary(per_case, stats)
    gov = governed_state(per_case)
    decision = {"D1_every_step_agrees": not s["disagreements"], "INV-01_rust_deterministic": det,
                "INV-02_records_read_only_no_tmp": all(c["inv02"] for c in per_case),
                "INV-03_scoring_tree_unchanged": before == after, "INV-04_governed_state": all(gov.values()),
                "INV-05_synthetic_label": all(labels), "cargo_gate": gate["pass"],
                "reference_files_match": not refusals}
    verdict = "PARITY_PASS" if all(decision.values()) else "PARITY_FAIL"
    os.makedirs(REF_DIR, exist_ok=True)
    ref_path = os.path.join(REF_DIR, "python_outcomes_v1.json.gz")
    with open(ref_path, "wb") as f:
        f.write(gzip.compress((json.dumps(py_out, indent=1, sort_keys=True) + "\n").encode(), mtime=0))
    srcs = RUST_SOURCES + sorted(os.path.relpath(os.path.join(dp, f), REPO)
                                 for dp, _, fs in os.walk(os.path.join(REPO, "crates", "abep-hall", "src")) for f in fs)
    rep = {
        "schema": "abep_rust_parity_report_v1", "id": "PARITY-REPORT-C-HALL-MAP-ENSEMBLE-REGISTRY-V1",
        "contract": {"path": os.path.relpath(CONTRACT, REPO), "sha256": sha_file(CONTRACT),
                     "id": CONTRACT_DOC["id"],
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
        "environment": {"python": platform.python_version(), "numpy": __import__("numpy").__version__,
                        "scipy": __import__("scipy").__version__,
                        "requirements_lock_sha256": sha_file(os.path.join(REPO, "requirements-lock.txt")),
                        "thread_env": {k: os.environ.get(k, "unset") for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                                                               "MKL_NUM_THREADS")},
                        "platform": platform.platform(), "cpu_count": os.cpu_count()},
        "campaign_seeds": {"scoring_master_seed": seed, "random_maps": 240},
        "refusals": refusals, "decision": decision, "summary": s, "governed_state": gov,
        "classification_gate": {"forbidden_identifier_scan_crates_abep_hall": forbidden_scan() or "no hit"},
        "conservation": "NOT_APPLICABLE (contract conservation_checks.applicable = false)",
        "schema_parity": "REQUIRED_FIELDS / REQUIRED_META compared in S-01; record-key lists checked by abep-hall unit tests",
        "performance": {"status": "reported, not a decision criterion", "python_seconds": timing["py"],
                        "rust_seconds": timing["rs"], "campaign_wall_seconds": round(wall, 1)},
        "reference_outputs": {"path": os.path.relpath(ref_path, REPO), "sha256": sha_file(ref_path)},
        "verdict": verdict, "cargo_gate": gate, "admission": "ADMITTED" if verdict == "PARITY_PASS" else "NOT_ADMITTED",
        "campaign_history": [
            {"execution": "development", "seed": CONTRACT_DOC["campaign_seeds"]["development_master_seed"],
             "note": "development executions (development seed + catalogue) before scoring; never a verdict"},
            {"execution": "scoring", "seed": seed, "commit": commit,
             "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "verdict": verdict}],
        "ledger_update_requested": [
            {"component": c, "status": "ADMITTED" if verdict == "PARITY_PASS" else "PREREG_PARITY",
             "scope": scope, "authoritative_implementation": "rust: abep_hall" if verdict == "PARITY_PASS" else "python",
             "contract": os.path.relpath(CONTRACT, REPO), "contract_sha256": sha_file(CONTRACT),
             "report": os.path.relpath(REPORT_JSON, REPO)}
            for c, scope in [("C-ABEP_SIM_HALL_MAP_PY", "whole module"), ("C-ABEP_SIM_HALL_ENSEMBLE_PY", "whole module"),
                             ("C-ABEP_SIM_HALLMAP_REGISTRY_PY", "whole module"),
                             ("C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY",
                              "function subset hall_response_status only; the rest stays PYTHON_REFERENCE (SC-WP-10)")]],
        "results": per_case,
    }
    with open(REPORT_JSON, "w") as f:
        f.write(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    write_md(rep)
    print(verdict, json.dumps(decision))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "develop"
    {"develop": develop, "score": score}[mode]()
