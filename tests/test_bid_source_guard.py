"""bid_source_guard (scripts/ci_checks.py; A9.29 sec. 3, RM-OQ-11): the Python implementation, kept while Python CI exists.
The primary implementation is Rust (crates/abep-provenance/src/bid_guard.rs). Both read docs/bid/bid_source_manifest_v1.json
and run the cases preregistered in docs/rust_migration/contracts/BID_SOURCE_GUARD/acceptance_v1.json (development runs; the
acceptance report is produced once). Needs a full-history clone, like the rule-9 outcome: in a shallow clone the guard
reports history NOT_EVALUATED and these tests fail with that reason. Never skipped (CLAUDE.md rule 9 counts unchanged)."""
import hashlib
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("ci_checks_bid", os.path.join(ROOT, "scripts", "ci_checks.py"))
ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci)

ORIGINAL_CHECKS = ["parse_json_toml", "prereg_lock", "audit_manifest", "hallthruster_pin", "rate_validity_coverage",
                   "variant_configs", "p5_n2_cases", "launch_manifests", "multiply_charged_tables", "ensemble_gate",
                   "h2_6_live_sources"]


def test_registered_as_a_twelfth_check_beside_the_eleven():
    assert list(ci.CHECKS) == ORIGINAL_CHECKS + ["bid_source_guard"]


def test_guard_passes_on_the_repository():
    r = ci.bid_source_guard()
    assert r["overall"] == "PASS", json.dumps(r, indent=1)
    problems, note = ci.check_bid_source_guard()
    assert problems == [] and note.startswith("overall PASS")


def test_constants_match_the_preregistration_and_the_manifest():
    with open(os.path.join(ROOT, ci.BID_ACCEPTANCE), "rb") as f:
        data = f.read()
    assert hashlib.sha256(data).hexdigest() == ci.BID_ACCEPTANCE_SHA256
    g = json.loads(data)["semantics"]["governed_constants"]
    assert g["technical_source"] == ci.BID_TECHNICAL_SOURCE and g["terminal_package_state"] == ci.BID_TERMINAL
    assert g["package_lineage"] == ci.BID_LINEAGE and g["manifest_path"] == ci.BID_MANIFEST_PATH
    assert g["mission_scenario_v2"] == {"path": ci.BID_MISSION_PATH, "sha256": ci.BID_MISSION_SHA256}
    with open(os.path.join(ROOT, ci.BID_MANIFEST_PATH), "rb") as f:
        m = ci.bid_parse_manifest(f.read())
    assert m["authorizations"] == []                        # owner_change_authorizations starts empty
    assert sorted(m["lineage"][-1]["files"]) == sorted(
        os.path.relpath(os.path.join(d, n), ROOT).replace(os.sep, "/")
        for d, dirs, files in os.walk(os.path.join(ROOT, "docs", "bid")) if os.path.basename(d) != "__pycache__"
        for n in files if n != os.path.basename(ci.BID_MANIFEST_PATH))


def test_every_preregistered_case_holds():
    results = ci.bid_guard_acceptance()
    assert len(results) == 25
    failed = {r["id"]: r["problems"] for r in results if r["problems"]}
    assert not failed, failed
    passing = {r["id"] for r in results if r["summary"]["overall"] == "PASS"}
    assert passing == {"BASE-00", "BASE-01", "CTRL-01"}


def test_invalid_manifest_fails_both_parts(tmp_path):
    (tmp_path / "docs" / "bid").mkdir(parents=True)
    (tmp_path / ci.BID_MANIFEST_PATH).write_text('{"schema": "abep_bid_source_manifest_v1"}')
    r = ci.bid_source_guard(str(tmp_path), None, "HEAD")
    assert r["overall"] == "FAIL"
    assert [f["code"] for f in r["files"]["findings"]] == [f["code"] for f in r["history"]["findings"]] == [
        "MANIFEST_INVALID"]
