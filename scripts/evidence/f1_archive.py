#!/usr/bin/env python3
"""F1 intake-synthesis evidence archive (owner decision A9.22 item 9,
docs/decisions/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md item 9).

Builds the deterministic archive F1_<run-id>.tar.zst of the complete F1 output (f1_intake_synthesis_v1.json, 36.7 MB,
and its generated F1_INTAKE_SYNTHESIS.md) and the committed manifest F1_<run-id>.manifest.json (archive sha256 / size,
generating commit, architecture id / hash, design-state set id / hash, input-manifest hash, model-set / numerical-method
ids, command, timestamp, per-file sha256 manifest, evidence classification, storage identifiers). The archive is
re-extracted and every member compared byte for byte with the original BEFORE the manifest is written. Nothing is
deleted: the original stays in the working tree until the integrator has stored the archive retrievably and verified it.

Usage:
  python scripts/evidence/f1_archive.py build    # write archive + manifest (needs the full JSON and git history)
  python scripts/evidence/f1_archive.py verify   # exit 1 unless the committed manifest, the core view and (when
                                                 # present locally) the full JSON and the archive all agree
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


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def _canon_sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


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
                    "verify_archive": f"python {SCRIPT_REL} verify", "as_recorded_in_output": doc["regenerate"]},
        "architecture": {
            "id": A19.FLIGHT_CONFIGURATION,
            "sha256": _canon_sha(arch),
            "hash_rule": "sha256 of canonical JSON (sorted keys, compact separators) of "
                         "abep_sim/design/a9_19_architecture.py FLIGHT_ARCHITECTURE",
            "source": "abep_sim/design/a9_19_architecture.py (no config/ architecture record exists in this repository)",
            "module_git_blob": _git("rev-parse", f"HEAD:abep_sim/design/a9_19_architecture.py"),
            "module_git_blob_at_generating_commit": _git("rev-parse",
                                                         f"{GENERATING_COMMIT}:abep_sim/design/a9_19_architecture.py"),
            "decision_records": A19.cite("A9.19"),
            "note": "the F1 intake screening takes no architecture record as an input (its pins are the frozen data, the "
                    "design-state set and the A9.7 directive); the id records the flight architecture in force when "
                    "the output was generated"},
        "design_state_set": {"id": dss.get("id", isy.DESIGN_STATE_SET_ID), "path": isy.DESIGN_STATE_SET_REL,
                             "sha256": isy.DESIGN_STATE_SET_SHA256, "as_recorded_in_output": dss},
        "input_manifest": {"sha256": _canon_sha(doc["pins"]),
                           "hash_rule": "sha256 of canonical JSON (sorted keys, compact separators) of the output's "
                                        "pins list [{path, sha256}]",
                           "pins": doc["pins"], "referenced_not_pinned": doc["referenced_not_pinned"]},
        "model_set": {
            "model_set_id": "PENDING (no config/model_set record exists yet; A9.22 layer separation)",
            "output_schema": doc["schema"],
            "model_sources_at_generating_commit": {p: _git("rev-parse", f"{GENERATING_COMMIT}:{p}")
                                                   for p in MODEL_SOURCES},
            "frozen_data": [p for p in doc["pins"] if p["path"].startswith("abep_sim/data/")]},
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
                          "repository": "ppusapati/abep", "tag": RELEASE_TAG, "asset_name": ARCHIVE_NAME,
                          "status": "PENDING_OWNER_UPLOAD"},
            "git_lfs": {"path": ARCHIVE_REL, "gitattributes": LFS_RULE, "lfs_oid": f"sha256:{ea.sha256_bytes(blob)}",
                        "status": "POINTER_COMMITTED_OBJECT_NOT_UPLOADED (git lfs push origin <branch> by the "
                                  "integrator; this repository has no git-lfs pre-push hook installed)"},
            "original_full_file": {"path": isy.F1_FULL_REL, "sha256": full_entry["sha256"],
                                   "size_bytes": full_entry["size_bytes"],
                "removal_rule": "remove from the working tree / index only after the archive is stored retrievably and "
                                "re-downloaded and hash-verified byte for byte (python scripts/evidence/f1_archive.py "
                                "verify); never rewrite history"}},
        "verification": {"rule": "archive sha256 / size; zstd decode; tar sha256; every member re-extracted and "
                                 "compared by size, sha256 and byte for byte with the original; deterministic member "
                                 "metadata", "result_at_build": "VERIFIED"},
    }


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


def build() -> int:
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
    errs = ea.verify_archive(blob, man, originals=dict(members))       # verify BEFORE writing anything
    if errs:
        raise SystemExit("REFUSED: archive verification failed: " + "; ".join(errs))
    out = REPO / ARCHIVE_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    if ea.verify_archive(out.read_bytes(), man, originals=dict(members)):
        raise SystemExit("REFUSED: archive on disk does not verify")
    (REPO / MANIFEST_REL).write_text(dump(man), encoding="utf-8")
    print(f"wrote {ARCHIVE_REL} ({len(blob)} B, sha256 {man['archive']['sha256']}) and {MANIFEST_REL}")
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="F1 evidence archive (A9.22 item 9)")
    ap.add_argument("action", choices=("build", "verify"))
    a = ap.parse_args(argv)
    return build() if a.action == "build" else verify()


if __name__ == "__main__":
    sys.exit(main())
