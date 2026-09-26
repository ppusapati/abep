"""O4 staged-sensitivity and escalation datasets: freeze, then score ONCE against the frozen mandatory vacuum dataset
(owner decision 2026-09-26; the pre-registered rule O4_staged_escalation is applied unchanged by the frozen scorer).

  freeze:  the launch manifest must equal a fresh build of the pinned manifests (scripts/make_p5_n2_launch_manifests.py)
           -> structural gate make_p5_n2_launch_manifests.check(manifest, shards) must PASS (keys, mode, smoke, lock, HT commit)
           -> record identity (freeze_p5_n2_dataset.record_identity) -> canonical merge (untouched lines sorted by key) + SHA256
           -> deterministic gzip (mtime 0) + freeze manifest. Nothing in a record is read beyond its identity fields.
  score:   both datasets are re-verified against their freeze manifests; the mandatory dataset must already carry its
           score-once provenance; the scorer must be byte-identical to the frozen scorer (10842ce). The scorer runs on
           mandatory + staged records: its `candidates`/`runs` must reproduce the official mandatory scores exactly, and its
           `staged_escalation` block is the O4 trigger evaluation. The provenance manifest (renamed last) binds both inputs.
The facility campaign (mandatory chemistry, facility mode) uses the standard pipeline (freeze_p5_n2_dataset.py facility ...,
score_p5_n2_frozen.py); this script is for the vacuum O4 datasets only. Nothing is decided here: dispositions are recorded
separately by the owner (ensemble/o4_dispositions_schema_v1.json) and are required before any admission.
Usage: python scripts/score_p5_n2_staged.py freeze <launch_manifest.json> <shard.jsonl ...> [--tag v1]
       python scripts/score_p5_n2_staged.py score <staged_raw_manifest.json>
"""
import datetime, gzip, hashlib, importlib.util, io, json, os, sys, tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
BR = os.path.join(ROOT, "hallthruster_bridge")
VAL = os.path.join(BR, "validation")
MANDATORY = os.path.join(VAL, "p5_n2_campaign_v1_vacuum_raw_manifest.json")
h = lambda b: hashlib.sha256(b).hexdigest()


def _mod(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(os.path.abspath(__file__)), fname))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


fz = _mod("freeze_p5_n2_dataset", "freeze_p5_n2_dataset.py")
sf = _mod("score_p5_n2_frozen", "score_p5_n2_frozen.py")
mm = _mod("make_p5_n2_launch_manifests", "make_p5_n2_launch_manifests.py")


def freeze_staged(manifest_path, paths, tag="v1", outdir=VAL, check_code=True):
    man = json.load(open(manifest_path))
    fresh = {m["name"]: json.loads(json.dumps(m)) for m in mm.build()}
    if fresh.get(man.get("name")) != man:
        raise SystemExit(f"launch manifest {manifest_path} differs from the pinned build")
    if man["mode"] != "vacuum" or not (man["name"].startswith("staged_") or man["name"].startswith("escalation_")):
        raise SystemExit("only vacuum staged/escalation datasets are frozen here (facility: freeze_p5_n2_dataset.py)")
    ident = fz.code_identity()
    if check_code and not all(v["identical"] for v in ident.values()):
        raise SystemExit("pipeline code differs from the pinned chain: " + json.dumps(ident))
    gate = mm.check(man, paths)
    if not gate["PASS"]:
        raise SystemExit("structural gate FAILED: " + json.dumps({k: v for k, v in gate.items() if k != "missing"}))
    mism = fz.record_identity(paths)
    if mism:
        raise SystemExit(f"record identity check FAILED ({len(mism)} records): " + json.dumps(mism[:5]))
    data, n = fz.canonical(paths)
    stem = os.path.join(outdir, f"p5_n2_campaign_{tag}_{man['name']}_raw")
    gz_path, man_path = stem + ".jsonl.gz", stem + "_manifest.json"
    if os.path.exists(gz_path) or os.path.exists(man_path):
        raise SystemExit(f"refusing to overwrite a frozen dataset: {gz_path}")
    os.makedirs(outdir, exist_ok=True)
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        gz.write(data)
    open(gz_path, "wb").write(buf.getvalue())
    lock = os.path.join(BR, "prereg", "p5_n2_prereg_lock_v1.json")
    fm = {"dataset": os.path.relpath(gz_path, BR), "mode": man["mode"], "n_records": n,
          "sha256_canonical_jsonl": h(data), "sha256_gz": h(buf.getvalue()),
          "canonical_form": "untouched raw record lines, one per line, sorted by key (byte order of the key string)",
          "launch_manifest": os.path.relpath(os.path.abspath(manifest_path), os.path.abspath(BR)),
          "launch_manifest_sha256": h(open(manifest_path, "rb").read()),
          "o4": {k: man[k] for k in ("role", "chemistry", "baseline", "compare_with", "sensitivity") if k in man},
          "prereg_lock_sha256": h(open(lock, "rb").read()),
          "structural_gate": {k: gate[k] for k in ("PASS", "n_records", "n_expected", "retcode_counts")},
          "record_identity_check": {"PASS": True, "rule": "identity fields == key fields == pinned case metadata"},
          "frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), **fz.PROVENANCE}
    fm["code_as_run"] = dict(ident, staged={"file": "scripts/score_p5_n2_staged.py",
                                            "sha256": h(open(os.path.abspath(__file__), "rb").read())})
    fm["chain_consistent"] = all(v["identical"] for v in ident.values())
    json.dump(fm, open(man_path, "w"), indent=1)
    return fm


def _raw(man):
    raw = gzip.decompress(open(os.path.join(BR, man["dataset"]), "rb").read())
    if h(raw) != man["sha256_canonical_jsonl"]:
        raise SystemExit(f"{man['dataset']}: SHA256 does not match its freeze manifest")
    return raw


def score_staged(staged_manifest_path, mandatory_manifest_path=MANDATORY):
    sm, mman = json.load(open(staged_manifest_path)), json.load(open(mandatory_manifest_path))
    raw_s, raw_m = _raw(sm), _raw(mman)
    lock = h(open(os.path.join(BR, "prereg", "p5_n2_prereg_lock_v1.json"), "rb").read())
    if not lock == sm["prereg_lock_sha256"] == mman["prereg_lock_sha256"]:
        raise SystemExit("pre-registration lock changed since a dataset was frozen")
    m_stem = mandatory_manifest_path.replace("_raw_manifest.json", "")
    m_prov_path = m_stem + "_scores_provenance.json"
    if not os.path.isfile(m_prov_path):
        raise SystemExit("the mandatory dataset has no score-once provenance: score it first")
    m_prov = json.load(open(m_prov_path))
    m_scores_path = os.path.join(BR, m_prov["output"])
    if m_prov["input_sha256_canonical_jsonl"] != mman["sha256_canonical_jsonl"] or \
            h(open(m_scores_path, "rb").read()) != m_prov["output_sha256"]:
        raise SystemExit("mandatory scores are not bound to the mandatory frozen dataset")
    exp = mman["code_as_run"]["scorer"]
    cur = h(open(sf.SCORER, "rb").read())
    if not exp.get("identical") or cur != exp["expected_sha256"] or cur != sf._blob_sha256(mman["scorer_commit"], exp["file"]) \
            or sm["code_as_run"]["scorer"]["expected_sha256"] != cur:
        raise SystemExit(f"scorer differs from the frozen scorer at {mman['scorer_commit']}: refusing to score")
    stem = staged_manifest_path.replace("_raw_manifest.json", "")
    out, prov = stem + "_scores.json", stem + "_scores_provenance.json"
    if os.path.exists(prov):
        raise SystemExit(f"already scored (score once): {prov}")
    if os.path.exists(out):
        os.unlink(out)                           # orphan of an interrupted attempt (no provenance = not official)
    tmps = []
    for raw in (raw_m, raw_s):
        with tempfile.NamedTemporaryFile("wb", suffix=".jsonl", delete=False) as t:
            t.write(raw); tmps.append(t.name)
    s = sf._load_scorer()
    tmp_out, tmp_prov = out + f".partial-{os.getpid()}", prov + f".partial-{os.getpid()}"
    try:
        s.main([tmps[0], tmps[1], "--out", tmp_out])
        res, off = json.load(open(tmp_out)), json.load(open(m_scores_path))
        if res["candidates"] != off["candidates"] or res["runs"] != off["runs"]:
            raise SystemExit("mandatory scores are not reproduced exactly: refusing to publish")
        chem = list(sm["o4"]["chemistry"])
        if [c for c in chem if c not in res["staged_escalation"]]:
            raise SystemExit("the scorer produced no O4 evaluation for " + ", ".join(chem))
        p = {"input_dataset": sm["dataset"], "input_sha256_canonical_jsonl": sm["sha256_canonical_jsonl"],
             "input_n_records": sm["n_records"], "mode": sm["mode"], "o4": sm["o4"],
             "input_mandatory_dataset": mman["dataset"], "input_mandatory_sha256": mman["sha256_canonical_jsonl"],
             "mandatory_scores_sha256": m_prov["output_sha256"], "mandatory_reproduced": True,
             "scorer": os.path.relpath(sf.SCORER, ROOT), "scorer_sha256": cur, "scorer_expected_commit": mman["scorer_commit"],
             "prereg_lock_sha256": lock,
             "scored_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
             "output": os.path.relpath(out, BR), "output_sha256": h(open(tmp_out, "rb").read()),
             "o4_trigger_fired": {c: res["staged_escalation"][c]["trigger_fired"] for c in chem},
             "chain": {k: mman[k] for k in ("driver_commit", "integrity_gate_commit", "scorer_commit", "preregistration")}}
        with open(tmp_prov, "w") as fh:
            json.dump(p, fh, indent=1)
        os.replace(tmp_out, out)
        try:
            os.replace(tmp_prov, prov)           # the provenance rename commits the result
        except BaseException:
            if os.path.exists(out):
                os.unlink(out)
            raise
    finally:
        for f in tmps + [tmp_out, tmp_prov]:
            if os.path.exists(f):
                os.unlink(f)
    return p


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "freeze":
        tag = a[a.index("--tag") + 1] if "--tag" in a else "v1"
        files = [x for i, x in enumerate(a[2:], 2) if not x.startswith("--") and a[i - 1] != "--tag"]
        print(json.dumps(freeze_staged(a[1], files, tag), indent=1))
    elif a and a[0] == "score":
        print(json.dumps(score_staged(a[1]), indent=1))
    else:
        raise SystemExit(__doc__)
