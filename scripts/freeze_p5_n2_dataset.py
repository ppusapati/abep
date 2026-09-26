"""Freeze a completed P5-N2 campaign record set BEFORE it is scored (owner decision 2026-09-26).

  raw shard JSONLs -> structural integrity gate (scripts/audit_p5_n2_campaign_records.py) must PASS
  -> record identity check: every record's identity fields equal its key and the pinned case metadata
  -> canonical merge: the untouched raw lines, sorted by key; any duplicate key (identical or conflicting) is refused
  -> SHA256 of the canonical JSONL -> deterministic gzip (mtime 0) -> manifest binding the provenance chain.
Nothing in a record is read beyond its key; no record is modified.
Usage: python scripts/freeze_p5_n2_dataset.py <mode> <shard.jsonl ...> [--tag v1]
Writes hallthruster_bridge/validation/p5_n2_campaign_<tag>_<mode>_raw.jsonl.gz and ..._raw_manifest.json (refuses to overwrite).
"""
import gzip, hashlib, importlib.util, io, json, os, sys, datetime

ROOT = os.path.join(os.path.dirname(__file__), "..")
BR = os.path.join(ROOT, "hallthruster_bridge")
OUTDIR = os.path.join(BR, "validation")
PROVENANCE = {   # owner-recorded chain for the v1 vacuum dataset; the manifest also records the code actually used (code_as_run)
    "driver_commit": "79d4e128bfb9ad672dc8e6e81a6e88445bc5b62a",
    "integrity_gate_commit": "fcd6720ce8de6f33c0348e9f46144c8e27330a8b",
    "scorer_commit": "10842ce1fca42c260f902ebd038b8379db9fe0ac",
    "preregistration": "PR #27 (17a99cd), prereg/p5_n2_validation_criteria_v1.json",
}


def _last_commit(path):
    import subprocess
    try:
        return subprocess.run(["git", "log", "-1", "--format=%H", "--", path], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None
    except OSError:
        return None


def blob_sha256(commit, relpath):
    """sha256 of a file's content at a commit (None if unavailable)."""
    import subprocess
    r = subprocess.run(["git", "show", f"{commit}:{relpath}"], cwd=ROOT, capture_output=True)
    return hashlib.sha256(r.stdout).hexdigest() if r.returncode == 0 else None


CODE = {"integrity_gate": ("scripts/audit_p5_n2_campaign_records.py", "integrity_gate_commit"),
        "scorer": ("scripts/score_p5_n2_campaign.py", "scorer_commit")}


def code_identity():
    """Each pipeline file must be byte-identical to its content at the pinned chain commit."""
    out = {}
    for name, (rel, key) in CODE.items():
        cur = hashlib.sha256(open(os.path.join(ROOT, rel), "rb").read()).hexdigest()
        exp = blob_sha256(PROVENANCE[key], rel)
        out[name] = {"file": rel, "sha256": cur, "expected_commit": PROVENANCE[key], "expected_sha256": exp,
                     "last_commit": _last_commit(os.path.join(ROOT, rel)), "identical": cur == exp}
    return out


def _gate():
    spec = importlib.util.spec_from_file_location("g", os.path.join(os.path.dirname(__file__), "audit_p5_n2_campaign_records.py"))
    g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
    return g


def record_identity(paths):
    """Every record's identity fields must equal those encoded in its key AND the pinned case metadata (cases/p5_n2.json):
    a permutation of candidate / chemistry / case / point / registration / coil_shape / mode fields is refused (PR #29 review).
    Reads identity fields only."""
    cases = {c["id"]: c for c in json.load(open(os.path.join(BR, "cases", "p5_n2.json")))["cases"]}
    bad = []
    for p in paths:
        for line in open(p):
            if not line.strip():
                continue
            r = json.loads(line)
            cand, chem, case, mode = r["key"].split("|")
            c = cases.get(case)
            exp = {"candidate": cand, "chemistry": chem, "case": case, "mode": mode}
            if c is not None:
                exp.update({"point": c["point"], "registration": c["registration"], "coil_shape": c["coil_shape"]})
            else:
                bad.append((r["key"], "case not in cases/p5_n2.json"))
            wrong = {k: r.get(k) for k, v in exp.items() if r.get(k) != v}
            if wrong:
                bad.append((r["key"], wrong))
    return bad


def canonical(paths):
    """(canonical bytes, n) from the untouched raw lines sorted by key; raises on any duplicate key."""
    lines = {}
    for p in paths:
        with open(p, "rb") as fh:
            for raw in fh:
                if not raw.strip():
                    continue
                raw = raw.rstrip(b"\n") + b"\n"
                key = json.loads(raw)["key"]
                if key in lines:
                    kind = "identical" if lines[key] == raw else "CONFLICTING"
                    raise SystemExit(f"duplicate key ({kind}): {key}")
                lines[key] = raw
    return b"".join(lines[k] for k in sorted(lines)), len(lines)


def freeze(mode, paths, tag="v1", outdir=OUTDIR, check_code=True):
    ident = code_identity()
    if check_code and not all(v["identical"] for v in ident.values()):
        raise SystemExit("pipeline code differs from the pinned chain: " + json.dumps(ident))
    gate = _gate().audit(mode, paths)
    if not gate["PASS"]:
        raise SystemExit("structural integrity gate FAILED: " + json.dumps({k: v for k, v in gate.items() if k != "missing"}))
    mism = record_identity(paths)
    if mism:
        raise SystemExit(f"record identity check FAILED ({len(mism)} records): " + json.dumps(mism[:5]))
    data, n = canonical(paths)
    stem = os.path.join(outdir, f"p5_n2_campaign_{tag}_{mode}_raw")
    gz_path, man_path = stem + ".jsonl.gz", stem + "_manifest.json"
    if os.path.exists(gz_path) or os.path.exists(man_path):
        raise SystemExit(f"refusing to overwrite a frozen dataset: {gz_path}")
    os.makedirs(outdir, exist_ok=True)
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        gz.write(data)
    open(gz_path, "xb").write(buf.getvalue())          # exclusive creation: never overwrites
    lock = os.path.join(BR, "prereg", "p5_n2_prereg_lock_v1.json")
    man = {"dataset": os.path.relpath(gz_path, BR), "mode": mode, "n_records": n,
           "sha256_canonical_jsonl": hashlib.sha256(data).hexdigest(), "sha256_gz": hashlib.sha256(buf.getvalue()).hexdigest(),
           "canonical_form": "untouched raw record lines, one per line, sorted by key (byte order of the key string)",
           "prereg_lock_sha256": hashlib.sha256(open(lock, "rb").read()).hexdigest(),
           "integrity_gate": {k: gate[k] for k in ("PASS", "n_records", "n_expected", "retcode_counts", "grid")},
           "record_identity_check": {"PASS": True, "rule": "identity fields == key fields == pinned case metadata"},
           "frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), **PROVENANCE}
    man["code_as_run"] = dict(ident, freeze={"file": "scripts/freeze_p5_n2_dataset.py",
                                              "sha256": hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest(),
                                              "last_commit": _last_commit(os.path.abspath(__file__))})
    man["chain_consistent"] = all(v["identical"] for v in ident.values())
    json.dump(man, open(man_path, "x"), indent=1)
    return man


if __name__ == "__main__":
    args = sys.argv[1:]
    tag = args[args.index("--tag") + 1] if "--tag" in args else "v1"
    files = [a for i, a in enumerate(args[1:], 1) if not a.startswith("--") and args[i - 1] != "--tag"]
    print(json.dumps(freeze(args[0], files, tag), indent=1))
