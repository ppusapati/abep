"""Validation release manifest (owner decision 2026-09-26): generated only AFTER scoring. It binds the complete chain

  pre-registration -> driver -> raw dataset -> dataset SHA -> integrity gate -> scorer -> scores SHA -> decision -> admission records

and verifies every link before writing anything. It is a manifest, not an interpretation: the only result content it carries is
a copy of the mechanical decision's candidate lists. Refuses to overwrite an existing release; published atomically
(temporary file -> parse/verify -> os.replace), so an interruption cannot leave a truncated release that blocks a retry.
Usage: python scripts/make_validation_release.py <freeze_manifest.json> [--out VALIDATION_RELEASE_v1.json]
(the scores / provenance / decision / report files are located next to the freeze manifest by the standard names)
"""
import hashlib, json, os, subprocess, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
BR = os.path.join(ROOT, "hallthruster_bridge")
h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()


def _blob_sha256(commit, relpath):
    r = subprocess.run(["git", "show", f"{commit}:{relpath}"], cwd=ROOT, capture_output=True)
    return hashlib.sha256(r.stdout).hexdigest() if r.returncode == 0 else None


def release(freeze_manifest, bridge_dir=BR, ensemble_members=None, check_git=True):
    fail = []
    man = json.load(open(freeze_manifest))
    stem = freeze_manifest.replace("_raw_manifest.json", "")
    paths = {"dataset": os.path.join(bridge_dir, man["dataset"]), "scores": stem + "_scores.json",
             "scores_provenance": stem + "_scores_provenance.json", "decision": stem + "_scores_decision.json",
             "report": stem + "_scores_report.md"}
    for k, p in paths.items():
        if not os.path.isfile(p):
            fail.append(f"missing {k}: {p}")
    if fail:
        raise SystemExit("release refused: " + "; ".join(fail))
    import gzip
    raw_sha = hashlib.sha256(gzip.decompress(open(paths["dataset"], "rb").read())).hexdigest()
    prov = json.load(open(paths["scores_provenance"]))
    dec = json.load(open(paths["decision"]))
    scores_sha = h(paths["scores"])
    lock_path = os.path.join(bridge_dir, "prereg", "p5_n2_prereg_lock_v1.json")
    checks = {
        "dataset_sha_matches_freeze": raw_sha == man["sha256_canonical_jsonl"],
        "provenance_input_is_dataset": prov["input_sha256_canonical_jsonl"] == man["sha256_canonical_jsonl"],
        "scores_sha_matches_provenance": scores_sha == prov["output_sha256"],
        "decision_bound_to_scores": dec.get("source_scores_sha256") == scores_sha,
        "decision_names_provenance": (dec.get("scores_provenance") or {}).get("sha256") == h(paths["scores_provenance"]),
        "lock_unchanged": h(lock_path) == man["prereg_lock_sha256"] == prov["prereg_lock_sha256"],
        "code_identity_at_freeze": bool(man.get("chain_consistent")),
        "scorer_identity_at_scoring": prov["scorer_sha256"] == man["code_as_run"]["scorer"]["expected_sha256"],
    }
    if check_git:
        checks["driver_commit_resolves"] = _blob_sha256(man["driver_commit"], "hallthruster_bridge/campaign/p5_n2_campaign.jl") is not None
    adm = []
    for m in (ensemble_members or []):
        a = m.get("admission") or {}
        if a.get("decision_sha256") == h(paths["decision"]):
            adm.append({"ensemble_member_id": m["ensemble_member_id"], "passing_layer1_members": a.get("passing_layer1_members"),
                        "admitted_utc": a.get("admitted_utc"), "decided_by": a.get("decided_by")})
    checks["admissions_subset_of_promotable"] = all(x["ensemble_member_id"] in dec.get("promotable", []) for x in adm)
    bad = [k for k, v in checks.items() if not v]
    if bad:
        raise SystemExit("release refused, broken links: " + ", ".join(bad))
    rel = lambda p: os.path.relpath(p, bridge_dir)
    return {"release": "VALIDATION_RELEASE", "campaign": os.path.basename(stem), "mode": man["mode"],
            "preregistration": {"criteria": man["preregistration"], "lock_sha256": man["prereg_lock_sha256"]},
            "driver_commit": man["driver_commit"],
            "dataset": {"file": rel(paths["dataset"]), "n_records": man["n_records"], "sha256_canonical_jsonl": raw_sha,
                        "freeze_manifest": rel(freeze_manifest), "freeze_manifest_sha256": h(freeze_manifest)},
            "integrity_gate": man["code_as_run"]["integrity_gate"], "scorer": man["code_as_run"]["scorer"],
            "scores": {"file": rel(paths["scores"]), "sha256": scores_sha, "scored_utc": prov["scored_utc"],
                       "provenance": rel(paths["scores_provenance"]), "provenance_sha256": h(paths["scores_provenance"])},
            "decision": {"file": rel(paths["decision"]), "sha256": h(paths["decision"]), "promotable": dec.get("promotable"),
                         "inconclusive": dec.get("inconclusive"), "failed_validation": dec.get("failed_validation")},
            "report": {"file": rel(paths["report"]), "sha256": h(paths["report"])},
            "admission_records": adm, "link_checks": checks}


def publish(r, out):
    """Atomic publication: temporary file -> parse/verify -> os.replace. An interruption never leaves a truncated release."""
    tmp = out + f".partial-{os.getpid()}"
    try:
        with open(tmp, "w") as fh:
            json.dump(r, fh, indent=1)
        if json.load(open(tmp)) != json.loads(json.dumps(r)):
            raise SystemExit("release verification failed")
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


if __name__ == "__main__":
    fm = sys.argv[1]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(BR, "validation", "VALIDATION_RELEASE_v1.json")
    if os.path.exists(out):
        raise SystemExit(f"refusing to overwrite {out}")
    sys.path.insert(0, ROOT)
    from abep_sim.hall_ensemble import load_ensemble
    r = release(fm, ensemble_members=load_ensemble()["members"])
    publish(r, out)
    print(out)
