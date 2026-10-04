#!/usr/bin/env python3
"""F1 intake-synthesis evidence archive (owner decision A9.22 item 9,
docs/decisions/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md item 9).

Builds the deterministic archive F1_<run-id>.tar.zst of the complete F1 output (f1_intake_synthesis_v1.json, 36.7 MB,
and its generated F1_INTAKE_SYNTHESIS.md) and the committed manifest F1_<run-id>.manifest.json (archive sha256 / size,
generating commit, architecture id / hash, design-state set id / hash, input-manifest hash, model-set / numerical-method
ids, command, timestamp, per-file sha256 manifest, evidence classification, storage identifiers). The archive is
re-extracted and every member compared byte for byte with the original BEFORE the manifest is written. Nothing is
deleted: the original stays in the working tree until the integrator has stored the archive retrievably and verified it.

A9.24 item 11 (docs/decisions/OD_2026_10_04_A9_24_RUST_MIGRATION_AND_OPEN_ITEMS_OWNER_DECISIONS.md): AUTHORIZED TO KEEP
AND UPLOAD as a GitHub Release asset (tag RELEASE_TAG); never an ordinary Git blob; the upload is authoritative only after
a downloaded copy has been hash-verified (`verify-download`) and that record is committed.

Usage:
  python scripts/evidence/f1_archive.py build [--out-dir DIR] [--check]
        # build the archive; write it to DIR (default: the gitignored ARCHIVE_REL) and the manifest; with --check write
        # no manifest and exit 1 unless the rebuilt manifest equals the committed one byte for byte
  python scripts/evidence/f1_archive.py verify   # exit 1 unless the committed manifest, the core view and (when
                                                 # present locally) the full JSON and the archive all agree
  python scripts/evidence/f1_archive.py verify-download PATH [--record OUT.json]
        # check a downloaded copy against the committed manifest (sha256, size, zstd decode, tar sha256, every member's
        # size / sha256, deterministic member metadata, and byte for byte against the originals when present) and print
        # a JSON verification record the owner can commit (exit 1 on any mismatch)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import evidence_archive as ea  # noqa: E402
from abep_sim.design import a9_19_architecture as A19  # noqa: E402
from abep_sim.design import intake_synthesis as isy  # noqa: E402

SCRIPT_REL = "scripts/evidence/f1_archive.py"
DECISION = {"md": "docs/decisions/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md",
            "json": "docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json", "item": 9}
RUN_ID = isy.F1_RUN_ID
ARCHIVE_NAME = f"F1_{RUN_ID}.tar.zst"
ARCHIVE_REL = f"{isy.F1_ARCHIVE_DIR_REL}/{ARCHIVE_NAME}"
MANIFEST_REL = isy.F1_ARCHIVE_MANIFEST_REL
MD_REL = f"{isy.F1_DIR_REL}/F1_INTAKE_SYNTHESIS.md"
# The commit whose builder run produced the archived output (git log of f1_intake_synthesis_v1.json: blob a04f619
# first appears there); merged by 633f136, unchanged at 32c9e63 and later. Its author time is the generation timestamp
# (the JSON itself carries none) and the fixed tar mtime.
GENERATING_COMMIT = "405296ee4aeb42d8421c98aa3b7f164733fb7960"
GENERATING_COMMIT_EPOCH = 1791020893
GENERATING_COMMIT_TIME = "2026-10-03T09:48:13+00:00"
INTEGRATION_COMMITS = {"633f136": "merge of the design-state set v2 lane 405296e",
                       "32c9e639268df6bba10852d94e64983e73d0cac6": "integration (F4 -> F7/F8 / F9 rebuilt on this F1 output)"}
MEMBERS = ((f"F1_{RUN_ID}/f1_intake_synthesis_v1.json", isy.F1_FULL_REL),
           (f"F1_{RUN_ID}/F1_INTAKE_SYNTHESIS.md", MD_REL))
MODEL_SOURCES = ("abep_sim/design/intake_synthesis.py", "abep_sim/intake_tpmc.py", "abep_sim/atmosphere.py",
                 "abep_sim/constants.py", f"{isy.F1_DIR_REL}/build_f1_intake.py")
RELEASE_TAG = f"evidence-f1-{RUN_ID.lower().replace('_', '-')}"
LFS_RULE = "docs/evidence_archives/**/*.tar.zst filter=lfs diff=lfs merge=lfs -text"
LFS_STATUS = ("NOT_USED_LFS_UPLOAD_REFUSED_BY_ENVIRONMENT (2026-10-03: the LFS verify call was refused (403) from the remote "
              "execution environment; no pointer is committed; the archive is reproduced byte-for-byte by `python "
              "scripts/evidence/f1_archive.py build` from the committed full JSON and uploaded by the owner as the release "
              "asset)")
# The commit that first committed this manifest (3b2072e, A9.22 G9). Values read "at" it keep the manifest reproducible
# from git alone (HEAD-dependent values are never written into the manifest).
MANIFEST_FIRST_COMMIT = "3b2072e324cd121f2d2a7d7ae1df1e4a23dc40d8"
# A9.24 item 11 cross-check commit: the execution-branch head when the A9.24 manifest fields were added (config/ exists
# there; it did not exist at the generating commit). Read with `git show`, so the record is reproducible.
CROSSCHECK_COMMIT = "4b5563b643aa2103d999484ce4ccf5e2eca040e3"
CONFIG_MODEL_SET_REL = "config/model_set/physics_model_set_v1.json"
CONFIG_ARCHITECTURE_REL = "config/architecture/hall_icp_neutralizer_v1.json"
CONFIG_DSS_REL = "config/environment/design_state_set_ref_v1.json"
A924 = {"md": "docs/decisions/OD_2026_10_04_A9_24_RUST_MIGRATION_AND_OPEN_ITEMS_OWNER_DECISIONS.md",
        "md_sha256": "9a2c950befd20dc38c63a3c56d4443ce7a30f1630903ada618b054638325b1d7",
        "json": "docs/decisions/OD_2026_10_04_A9_24_rust_migration_and_open_items_owner_decisions.json",
        "json_sha256": "fdbb4561ca8dc524e11200750c2c9c497865f8142f1697ae0146d2dae3e5cc3c", "item": 11,
        "json_item_key": "11_f1_archive"}
A924_QUOTES = ("AUTHORIZED TO KEEP AND UPLOAD.",
               "Do NOT store the 36.7 MB generated archive as an ordinary Git blob.",
               "Verify the uploaded/downloaded archive hash against the original before treating the upload as "
               "authoritative.")
REPOSITORY = "ppusapati/abep"
DOWNLOAD_URL = f"https://github.com/{REPOSITORY}/releases/download/{RELEASE_TAG}/{ARCHIVE_NAME}"
DOWNLOAD_RECORD_REL = f"{isy.F1_ARCHIVE_DIR_REL}/F1_{RUN_ID}.download_verification.json"
UPLOAD_STEPS_REL = f"{isy.F1_ARCHIVE_DIR_REL}/UPLOAD_STEPS.md"
# A9.24 item 11 required repository fields -> manifest JSON pointer
A924_REQUIRED = (
    ("archive filename", "/archive/file_name"), ("SHA-256", "/archive/sha256"),
    ("byte size (compressed)", "/archive/size_bytes"), ("byte size (tar)", "/archive/tar_size_bytes"),
    ("complete file manifest", "/files"), ("per-file hashes", "/files/*/sha256"),
    ("generating commit", "/generating_commit/sha"), ("architecture/config hash", "/architecture/sha256"),
    ("design-state-set hash", "/design_state_set/sha256"), ("model-set hash", "/model_set/sha256"),
    ("generation command", "/command/generate"), ("evidence classification", "/evidence_classification/evidence_class"),
    ("release/download reference", "/storage/preferred/download_url"))


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def _canon_sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _git_bytes(rev_path: str) -> bytes:
    return subprocess.run(["git", "show", rev_path], cwd=REPO, check=True, capture_output=True).stdout


def _norm(t: str) -> str:
    return " ".join(t.split())


def _a924_record() -> dict:
    """A9.24 item 11 authorization: decision files pinned by sha256, quotes verbatim (fail closed)."""
    for k in ("md", "json"):
        if hashlib.sha256((REPO / A924[k]).read_bytes()).hexdigest() != A924[k + "_sha256"]:
            raise SystemExit(f"REFUSED: {A924[k]} differs from its pinned sha256 (immutable decision record)")
    md = _norm((REPO / A924["md"]).read_text(encoding="utf-8"))
    for q in A924_QUOTES:
        if _norm(q) not in md:
            raise SystemExit(f"REFUSED: A9.24 quote not verbatim: {q!r}")
    js = json.loads((REPO / A924["json"]).read_text(encoding="utf-8"))
    ans = js["items"].get(A924["json_item_key"])
    if js.get("decided_by") != "owner" or not ans or not ans.startswith("AUTHORIZED TO KEEP AND UPLOAD"):
        raise SystemExit("REFUSED: A9.24 item 11 is not an owner authorization to keep and upload")
    return dict(A924, answer=ans, quotes=list(A924_QUOTES))


def _model_set(doc: dict) -> dict:
    srcs = {}
    for p in MODEL_SOURCES:
        b = _git_bytes(f"{GENERATING_COMMIT}:{p}")
        srcs[p] = {"git_blob": _git("rev-parse", f"{GENERATING_COMMIT}:{p}"), "sha256": ea.sha256_bytes(b),
                   "size_bytes": len(b)}
    frozen = [p for p in doc["pins"] if p["path"].startswith("abep_sim/data/")]
    basis = {"model_sources": {p: v["sha256"] for p, v in srcs.items()},
             "frozen_data": {p["path"]: p["sha256"] for p in frozen}}
    cfg_raw = _git_bytes(f"{CROSSCHECK_COMMIT}:{CONFIG_MODEL_SET_REL}")
    cfg = json.loads(cfg_raw)
    mods = {m["path"]: m["sha256"] for m in cfg["modules"]}
    data = {d["path"]: d["sha256"] for d in cfg["data"]}
    cross = {}
    for p, v in srcs.items():
        if p in mods:
            cross[p] = "SAME_CONTENT" if mods[p] == v["sha256"] else "CONTENT_CHANGED_SINCE_GENERATING_COMMIT"
        else:
            cross[p] = "NOT_IN_PHYSICS_MODEL_SET (design layer / builder; physics_model_set_v1 lists abep_sim/*.py only)"
    for p in frozen:
        cross[p["path"]] = ("NOT_LISTED" if p["path"] not in data else
                            "SAME_CONTENT" if data[p["path"]] == p["sha256"] else
                            "CONTENT_CHANGED_SINCE_GENERATING_COMMIT")
    return {
        "model_set_id": "NOT_REGISTERED_AT_GENERATING_COMMIT (no config/model_set record existed at "
                        f"{GENERATING_COMMIT[:7]}; config/ was introduced later by 2cbe2dd, A9.22 Phase A)",
        "sha256": _canon_sha(basis),
        "hash_rule": "sha256 of canonical JSON (sorted keys, compact separators) of {model_sources: {path: sha256 of the "
                     "file content at the generating commit}, frozen_data: {path: sha256 pinned by the output}} "
                     "(A9.24 item 11 model-set hash; computed from git, not from the working tree)",
        "hash_basis": basis,
        "output_schema": doc["schema"],
        "model_sources_at_generating_commit": {p: v["git_blob"] for p, v in srcs.items()},
        "model_sources_content_at_generating_commit": srcs,
        "frozen_data": frozen,
        "config_model_set_crosscheck": {
            "path": CONFIG_MODEL_SET_REL, "id": cfg["id"], "at_commit": CROSSCHECK_COMMIT,
            "sha256_at_commit": ea.sha256_bytes(cfg_raw),
            "role": "INFORMATIONAL (postdates the generating commit; not the model set the output was generated with)",
            "per_file": cross}}


def _item(doc, iid):
    return next(i for i in doc["items"] if i["id"] == iid)


def build_manifest(doc: dict, members: list[tuple[str, bytes]], tar_bytes: bytes, blob: bytes) -> dict:
    blobs = {}
    for name, rel in MEMBERS:
        blobs[name] = {"source_path": rel, "git_blob_at_generating_commit": _git("rev-parse", f"{GENERATING_COMMIT}:{rel}")}
    if _git("show", "-s", "--format=%at %aI", GENERATING_COMMIT) != f"{GENERATING_COMMIT_EPOCH} {GENERATING_COMMIT_TIME}":
        raise SystemExit("REFUSED: generating-commit time differs from the recorded constant")
    files = ea.file_manifest(members, blobs)
    full_entry = next(f for f in files if f["source_path"] == isy.F1_FULL_REL)
    arch = A19.FLIGHT_ARCHITECTURE
    dss = doc["coverage_rule"]["design_state_set"]
    core_raw = (REPO / isy.F1_CORE_REL).read_bytes()
    return {
        "schema": "evidence_archive_manifest_v1",
        "id": f"F1_{RUN_ID}",
        "run_id": RUN_ID,
        "decision": DECISION,
        "deliverable": {"id": doc["id"], "schema": doc["schema"], "lane": doc["lane"], "path": isy.F1_FULL_REL},
        "archive": {
            "file_name": ARCHIVE_NAME, "path": ARCHIVE_REL, "sha256": ea.sha256_bytes(blob), "size_bytes": len(blob),
            "tar_sha256": ea.sha256_bytes(tar_bytes), "tar_size_bytes": len(tar_bytes),
            "tar": {"format": "ustar", "entry_order": "sorted by path", "mtime": GENERATING_COMMIT_EPOCH, "uid": 0,
                    "gid": 0, "uname": "", "gname": "", "mode": "0644", "entries": "regular files only"},
            "compression": {"codec": "zstd", "level": ea.ZSTD_LEVEL, "threads": "single", "frame_checksum": True,
                            "content_size": True, **ea.zstd_versions(),
                            "determinism": "archive bytes reproduce for the same libzstd version; tar_sha256 for any"},
            "builder": f"python {SCRIPT_REL} build"},
        "generating_commit": {
            "sha": GENERATING_COMMIT, "basis": "first commit carrying the archived f1_intake_synthesis_v1.json bytes "
            "(git log); the builder run that produced them is that commit's F1 rebuild",
            "deliverable_base_commit": doc["base_commit"], "integrated_by": INTEGRATION_COMMITS},
        "generated_timestamp": {"value": GENERATING_COMMIT_TIME, "basis": "author time of the generating commit (the F1 "
                                "JSON records no wall-clock time; deterministic)"},
        "command": {"generate": f"python {isy.F1_DIR_REL}/build_f1_intake.py", "verify_full_rebuild":
                    f"python {isy.F1_DIR_REL}/build_f1_intake.py --check", "verify_core_view":
                    f"python {isy.F1_DIR_REL}/build_f1_intake.py --check-core", "archive": f"python {SCRIPT_REL} build",
                    "verify_archive": f"python {SCRIPT_REL} verify",
                    "verify_download": f"python {SCRIPT_REL} verify-download <downloaded file>",
                    "as_recorded_in_output": doc["regenerate"]},
        "architecture": {
            "id": A19.FLIGHT_CONFIGURATION,
            "sha256": _canon_sha(arch),
            "hash_rule": "sha256 of canonical JSON (sorted keys, compact separators) of "
                         "abep_sim/design/a9_19_architecture.py FLIGHT_ARCHITECTURE",
            "source": "abep_sim/design/a9_19_architecture.py (no config/ architecture record existed at the generating "
                      "commit; see config_crosscheck)",
            "module_git_blob": _git("rev-parse", f"{MANIFEST_FIRST_COMMIT}:abep_sim/design/a9_19_architecture.py"),
            "module_git_blob_rule": f"blob at the commit that first committed this manifest ({MANIFEST_FIRST_COMMIT[:7]})",
            "module_git_blob_at_generating_commit": _git("rev-parse",
                                                         f"{GENERATING_COMMIT}:abep_sim/design/a9_19_architecture.py"),
            "decision_records": A19.cite("A9.19"),
            "note": "the F1 intake screening takes no architecture record as an input (its pins are the frozen data, the "
                    "design-state set and the A9.7 directive); the id records the flight architecture in force when "
                    "the output was generated",
            "config_crosscheck": {
                "path": CONFIG_ARCHITECTURE_REL, "at_commit": CROSSCHECK_COMMIT,
                "sha256_at_commit": ea.sha256_bytes(_git_bytes(f"{CROSSCHECK_COMMIT}:{CONFIG_ARCHITECTURE_REL}")),
                "role": "INFORMATIONAL (config/ postdates the generating commit; the module constants load from this "
                        "file since 2cbe2dd with values unchanged)"}},
        "design_state_set": {"id": dss.get("id", isy.DESIGN_STATE_SET_ID), "path": isy.DESIGN_STATE_SET_REL,
                             "sha256": isy.DESIGN_STATE_SET_SHA256, "as_recorded_in_output": dss,
                             "config_crosscheck": _dss_crosscheck()},
        "input_manifest": {"sha256": _canon_sha(doc["pins"]),
                           "hash_rule": "sha256 of canonical JSON (sorted keys, compact separators) of the output's "
                                        "pins list [{path, sha256}]",
                           "pins": doc["pins"], "referenced_not_pinned": doc["referenced_not_pinned"]},
        "model_set": _model_set(doc),
        "numerical_methods": [
            {"id": "TPMC_DIRECT", "description": doc["coverage_rule"]["direct_tpmc"],
             "particles_per_point": {"item": "F1-P-12", "value": _item(doc, "F1-P-12")["value"]}},
            {"id": "FROZEN_SURFACE_EXACT_NODE", "description": doc["coverage_rule"]["frozen_surface"]},
            {"id": "PARETO_NONDOMINATED_FILTER", "description": doc["pareto_method"]["filter"],
             "noise_rule": doc["pareto_method"]["noise_rule"]},
            {"id": "UNCERTAINTY_CALIBRATION", "description": doc["uncertainty_calibration"]}],
        "files": files,
        "evidence_classification": {
            "status": doc["status"], "deliverable_status": doc["deliverable_status"], "evidence_class": "model-derived",
            "what_this_is_not": doc["what_this_is_not"]},
        "committed_in_git": {
            "manifest": MANIFEST_REL,
            "core_view": {"path": isy.F1_CORE_REL, "sha256": ea.sha256_bytes(core_raw), "size_bytes": len(core_raw),
                          "rule": "abep_sim/design/intake_synthesis.py core_from_full (lossless consumer view)"},
            "summary": isy.core_summary(doc), "markdown": MD_REL},
        "storage": {
            "preferred": {"kind": "GitHub Release asset on a tagged engineering-evidence release",
                          "repository": REPOSITORY, "tag": RELEASE_TAG, "asset_name": ARCHIVE_NAME,
                          "status": "AUTHORIZED_TO_UPLOAD (A9.24 item 11); upload is a manual owner step "
                                    "(" + UPLOAD_STEPS_REL + ")",
                          "download_url": DOWNLOAD_URL,
                          "download_url_rule": "standard GitHub release-asset URL for this repository, tag and asset "
                                               "name; valid only once the owner has published the release",
                          "authoritative": False,
                          "authoritative_rule": "the uploaded asset becomes the authoritative copy only after a "
                                                "downloaded copy is verified with `python " + SCRIPT_REL +
                                                " verify-download <path>` (sha256, size, zstd decode, tar sha256, "
                                                "per-member hashes) and that record is committed at " +
                                                DOWNLOAD_RECORD_REL,
                          "download_verification": "PENDING (no downloaded copy verified yet)"},
            "git_lfs": {"path": ARCHIVE_REL, "gitattributes": LFS_RULE, "lfs_oid": f"sha256:{ea.sha256_bytes(blob)}",
                        "status": LFS_STATUS},
            "original_full_file": {"path": isy.F1_FULL_REL, "sha256": full_entry["sha256"],
                                   "size_bytes": full_entry["size_bytes"],
                "removal_rule": "remove from the working tree / index only after the archive is stored retrievably and "
                                "re-downloaded and hash-verified byte for byte (python scripts/evidence/f1_archive.py "
                                "verify); never rewrite history"}},
        "verification": {"rule": "archive sha256 / size; zstd decode; tar sha256; every member re-extracted and "
                                 "compared by size, sha256 and byte for byte with the original; deterministic member "
                                 "metadata", "result_at_build": "VERIFIED"},
        "upload_authorization": _a924_record(),
    }


def _dss_crosscheck() -> dict:
    ref = json.loads(_git_bytes(f"{CROSSCHECK_COMMIT}:{CONFIG_DSS_REL}"))
    return {"path": CONFIG_DSS_REL, "at_commit": CROSSCHECK_COMMIT, "id": ref["id"], "sha256": ref["sha256"],
            "same_as_output": ref["id"] == isy.DESIGN_STATE_SET_ID and ref["sha256"] == isy.DESIGN_STATE_SET_SHA256}


def _ptr_values(man: dict, ptr: str) -> list:
    vals = [man]
    for t in ptr.strip("/").split("/"):
        nxt = []
        for v in vals:
            if t == "*" and isinstance(v, list):
                nxt += v
            elif isinstance(v, dict) and t in v:
                nxt.append(v[t])
        vals = nxt
    return vals


def a924_checklist(man: dict) -> list[dict]:
    """A9.24 item 11 required repository fields: PRESENT (non-empty) or MISSING per field (fail closed)."""
    out = []
    for name, ptr in A924_REQUIRED:
        vals = _ptr_values(man, ptr)
        ok = bool(vals) and all(v not in (None, "", [], {}) for v in vals)
        out.append({"field": name, "pointer": ptr, "status": "PRESENT" if ok else "MISSING"})
    return out


def _members() -> list[tuple[str, bytes]]:
    out = []
    for name, rel in MEMBERS:
        p = REPO / rel
        if not p.is_file():
            raise SystemExit(f"REFUSED: original missing: {rel}")
        out.append((name, p.read_bytes()))
    return out


def dump(obj) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def build(out_dir: str | None = None, check: bool = False) -> int:
    members = _members()
    full = dict(members)[MEMBERS[0][0]]
    doc = json.loads(full)
    core_txt = isy.core_text_from_full_bytes(full)
    if (REPO / isy.F1_CORE_REL).read_text(encoding="utf-8") != core_txt:
        raise SystemExit(f"REFUSED: {isy.F1_CORE_REL} is not the core view of the full output (run build_f1_intake.py "
                         "--write-core)")
    tar_bytes = ea.deterministic_tar(members, GENERATING_COMMIT_EPOCH)
    blob = ea.compress(tar_bytes)
    if ea.deterministic_tar(members, GENERATING_COMMIT_EPOCH) != tar_bytes or ea.compress(tar_bytes) != blob:
        raise SystemExit("REFUSED: archive is not reproducible within this run")
    man = build_manifest(doc, members, tar_bytes, blob)
    man["a9_24_item_11_checklist"] = a924_checklist(man)
    missing = [x["field"] for x in man["a9_24_item_11_checklist"] if x["status"] != "PRESENT"]
    if missing:
        raise SystemExit("REFUSED: A9.24 item 11 fields missing from the manifest: " + ", ".join(missing))
    errs = ea.verify_archive(blob, man, originals=dict(members))       # verify BEFORE writing anything
    if errs:
        raise SystemExit("REFUSED: archive verification failed: " + "; ".join(errs))
    out = Path(out_dir).resolve() / ARCHIVE_NAME if out_dir else REPO / ARCHIVE_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    if ea.verify_archive(out.read_bytes(), man, originals=dict(members)):
        raise SystemExit("REFUSED: archive on disk does not verify")
    print(f"wrote {out} ({len(blob)} B, sha256 {man['archive']['sha256']}, tar sha256 {man['archive']['tar_sha256']})")
    if check:
        committed = (REPO / MANIFEST_REL).read_text(encoding="utf-8")
        if committed != dump(man):
            print(f"STALE: {MANIFEST_REL} differs from the rebuilt manifest", file=sys.stderr)
            return 1
        print(f"OK: {MANIFEST_REL} reproduces; archive matches it")
        return 0
    (REPO / MANIFEST_REL).write_text(dump(man), encoding="utf-8")
    print(f"wrote {MANIFEST_REL}")
    return 0


def verify() -> int:
    """Committed manifest vs core view (always), vs the full JSON / MD (when present), vs the archive (when present and
    not an un-smudged LFS pointer)."""
    errs, notes = [], []
    man = json.loads((REPO / MANIFEST_REL).read_text(encoding="utf-8"))
    core_raw = (REPO / isy.F1_CORE_REL).read_bytes()
    cv = man["committed_in_git"]["core_view"]
    if ea.sha256_bytes(core_raw) != cv["sha256"] or len(core_raw) != cv["size_bytes"]:
        errs.append("core view differs from the manifest")
    core = json.loads(core_raw)
    fo = core["full_output"]
    fm = {f["source_path"]: f for f in man["files"]}
    if fo["sha256"] != fm[isy.F1_FULL_REL]["sha256"] or fo["size_bytes"] != fm[isy.F1_FULL_REL]["size_bytes"]:
        errs.append("core view full_output hash / size differ from the manifest file entry")
    originals = {}
    for name, rel in MEMBERS:
        p = REPO / rel
        if p.is_file():
            b = p.read_bytes()
            originals[name] = b
            if ea.sha256_bytes(b) != fm[rel]["sha256"] or len(b) != fm[rel]["size_bytes"]:
                errs.append(f"{rel} differs from the manifest")
        else:
            notes.append(f"{rel} not present locally (archived); not compared")
    ap = REPO / ARCHIVE_REL
    if ap.is_file() and not ea.is_lfs_pointer(ap):
        errs += ea.verify_archive(ap.read_bytes(), man, originals=originals if len(originals) == len(MEMBERS) else None)
    else:
        notes.append(f"{ARCHIVE_REL} not present locally (or an un-fetched LFS pointer); archive not re-extracted")
    for n in notes:
        print("NOTE", n, file=sys.stderr)
    for e in errs:
        print("MISMATCH", e, file=sys.stderr)
    print("OK" if not errs else "FAIL")
    return 0 if not errs else 1


def _observed_members(tar_bytes: bytes, man: dict) -> list[dict]:
    import io
    import tarfile
    want = {f["path"]: f for f in man["files"]}
    out = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tf:
        for ti in tf.getmembers():
            data = tf.extractfile(ti).read() if ti.isreg() else b""
            f = want.get(ti.name) or {}
            out.append({"path": ti.name, "size_bytes": len(data), "sha256": ea.sha256_bytes(data),
                        "manifest_sha256": f.get("sha256"),
                        "ok": ti.isreg() and f.get("sha256") == ea.sha256_bytes(data)
                        and f.get("size_bytes") == len(data)})
    return out


def verify_download(path: str, record: str | None = None) -> int:
    """A9.24 item 11: verify a downloaded copy of the release asset against the committed manifest and print a JSON
    record the owner can commit (DOWNLOAD_RECORD_REL). Never edits the manifest; exit 1 on any mismatch."""
    from datetime import datetime, timezone
    man = json.loads((REPO / MANIFEST_REL).read_text(encoding="utf-8"))
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"REFUSED: {path} is not a file")
    if ea.is_lfs_pointer(p):
        raise SystemExit(f"REFUSED: {path} is a Git LFS pointer, not the archive")
    blob = p.read_bytes()
    originals = {}
    for name, rel in MEMBERS:
        if (REPO / rel).is_file():
            originals[name] = (REPO / rel).read_bytes()
    use_orig = originals if len(originals) == len(MEMBERS) else None
    errs = ea.verify_archive(blob, man, originals=use_orig)
    a = man["archive"]
    checks = [
        {"check": "archive sha256 == manifest", "expected": a["sha256"], "observed": ea.sha256_bytes(blob)},
        {"check": "archive size == manifest", "expected": a["size_bytes"], "observed": len(blob)},
    ]
    tar_bytes = None
    try:
        tar_bytes = ea.decompress(blob)
        checks += [{"check": "zstd decode", "expected": "OK", "observed": "OK"},
                   {"check": "tar sha256 == manifest", "expected": a["tar_sha256"],
                    "observed": ea.sha256_bytes(tar_bytes)},
                   {"check": "tar size == manifest", "expected": a["tar_size_bytes"], "observed": len(tar_bytes)}]
    except Exception as e:  # noqa: BLE001 - recorded as a failed check
        checks.append({"check": "zstd decode", "expected": "OK", "observed": f"FAILED: {e}"})
    for c in checks:
        c["ok"] = c["expected"] == c["observed"]
    rec = {
        "schema": "evidence_archive_download_verification_v1",
        "manifest": MANIFEST_REL, "manifest_sha256": ea.sha256_bytes((REPO / MANIFEST_REL).read_bytes()),
        "archive_file_name": a["file_name"], "verified_file": p.name,
        "release": {"repository": REPOSITORY, "tag": RELEASE_TAG, "asset_name": ARCHIVE_NAME, "download_url": DOWNLOAD_URL},
        "checks": checks,
        "members": _observed_members(tar_bytes, man) if tar_bytes is not None else "NOT_EXTRACTED (zstd decode failed)",
        "member_rule": "every tar member re-extracted; size and sha256 equal the manifest per-file entry; deterministic "
                       "member metadata; byte for byte against the local originals when present",
        "compared_with_local_originals": use_orig is not None,
        "mismatches": errs,
        "result": "VERIFIED" if not errs and all(c["ok"] for c in checks) else "FAILED",
        "authoritative": not errs and all(c["ok"] for c in checks),
        "authority": "A9.24 item 11: the upload is authoritative only after this verification of a downloaded copy",
        "verified_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "tools": {"python": sys.version.split()[0], **ea.zstd_versions()},
        "commit_as": DOWNLOAD_RECORD_REL,
    }
    txt = dump(rec)
    if record:
        Path(record).write_text(txt, encoding="utf-8")
    sys.stdout.write(txt)
    return 0 if rec["result"] == "VERIFIED" else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="F1 evidence archive (A9.22 item 9; A9.24 item 11)")
    sub = ap.add_subparsers(dest="action", required=True)
    b = sub.add_parser("build", help="build the archive (+ manifest)")
    b.add_argument("--out-dir", help="write the archive here instead of the gitignored repository path")
    b.add_argument("--check", action="store_true", help="write no manifest; exit 1 unless it reproduces")
    sub.add_parser("verify", help="committed manifest vs core view / local originals / local archive")
    d = sub.add_parser("verify-download", help="verify a downloaded copy of the release asset; print a record")
    d.add_argument("path")
    d.add_argument("--record", help="also write the record to this file")
    a = ap.parse_args(argv)
    if a.action == "build":
        return build(a.out_dir, a.check)
    if a.action == "verify-download":
        return verify_download(a.path, a.record)
    return verify()


if __name__ == "__main__":
    sys.exit(main())
