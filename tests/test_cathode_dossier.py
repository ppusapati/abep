"""Structural and evidence-discipline checks for the cathode / neutralizer evidence dossier.

docs/evidence/cathode/cathode_evidence_v1.json must parse, and every numeric value in it must carry a resolvable source,
an evidence class (quantity_type, docs/EVIDENCE.md) and an evidence level. Values without evidence must be null with an
explicit TBD reason. These tests read only the repository; they need no network and run in well under a second.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOSSIER_DIR = ROOT / "docs" / "evidence" / "cathode"
JSON_PATH = DOSSIER_DIR / "cathode_evidence_v1.json"
MD_PATH = DOSSIER_DIR / "CATHODE_DOSSIER.md"

QUANTITY_TYPES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
VERIFICATION = {
    "read_in_retrieved_text",
    "secondary_citation",
    "title_only_verify",
    "repo_audit_record",
    "derived_by_this_lane",
    "code_constant",
}
PARAMETER_CATEGORIES = {
    "demonstrated_emission_current",
    "keeper_startup_power",
    "steady_heater_power",
    "gas_flow",
    "emitter_temperature",
    "environmental_exposure",
    "recovery_cleaning",
    "lifetime_basis",
}
REQUIRED_CANDIDATES = {
    "xe_lab6_hollow_cathode",
    "xe_bao_w_hollow_cathode",
    "c12a7_electride_cathode",
    "rf_plasma_cathode",
    "microwave_plasma_cathode",
    "air_fed_thermionic_hollow_cathode",
}
# Numeric leaves are allowed only as entry values or under these metadata keys.
NUMERIC_METADATA_KEYS = {"schema_version", "evidence_level"}


@pytest.fixture(scope="module")
def dossier():
    with open(JSON_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _walk_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_dicts(v)


def _entries(d):
    return [o for o in _walk_dicts(d) if "value" in o]


def _claims(d):
    return [o for o in _walk_dicts(d) if "claim" in o]


def _sources(d):
    return {s["id"]: s for s in d["sources"]}


def _all_ids(d):
    return [o["id"] for o in _walk_dicts(d) if "id" in o and isinstance(o["id"], str)]


def test_json_parses_and_has_top_level_blocks(dossier):
    for key in (
        "id",
        "policy",
        "baseline_decision",
        "electron_current_requirement",
        "candidates",
        "uncertainty_register",
        "hardware_test_gaps",
        "repo_model_crosscheck",
        "sources",
    ):
        assert key in dossier, key
    assert dossier["id"] == "cathode_evidence_v1"
    assert set(dossier["policy"]["quantity_types"]) == QUANTITY_TYPES


def test_sources_are_complete(dossier):
    ids = [s["id"] for s in dossier["sources"]]
    assert len(ids) == len(set(ids)), "duplicate source ids"
    for s in dossier["sources"]:
        assert s.get("citation"), s["id"]
        assert s.get("access"), s["id"]
        assert s.get("url") or s.get("doi") or s.get("repo_path"), s["id"]
        if s.get("retrieved") is True:
            assert re.fullmatch(r"[0-9a-f]{64}", s.get("sha256", "")), f"{s['id']}: retrieved source needs sha256"
            assert s.get("retrieved_on"), s["id"]


def test_ids_unique(dossier):
    ids = _all_ids(dossier)
    dup = {i for i in ids if ids.count(i) > 1}
    assert not dup, f"duplicate ids: {sorted(dup)}"


def test_every_numeric_value_has_source_and_evidence_class(dossier):
    sources = _sources(dossier)
    entry_ids = {e["id"] for e in _entries(dossier)}
    for e in _entries(dossier):
        eid = e.get("id", "<no id>")
        v = e["value"]
        if v is None:
            assert isinstance(e.get("tbd"), str) and e["tbd"].strip(), f"{eid}: null value needs a TBD reason"
            continue
        values = v if isinstance(v, list) else [v]
        assert values and all(_is_number(x) for x in values), f"{eid}: value must be a number or list of numbers"
        assert isinstance(e.get("unit"), str) and e["unit"].strip(), f"{eid}: unit"
        assert e.get("source_id") in sources, f"{eid}: unresolvable source_id {e.get('source_id')!r}"
        assert e.get("quantity_type") in QUANTITY_TYPES, f"{eid}: evidence class (quantity_type)"
        lvl = e.get("evidence_level")
        assert isinstance(lvl, int) and not isinstance(lvl, bool) and 1 <= lvl <= 7, f"{eid}: evidence_level"
        ver = e.get("verification")
        assert ver in VERIFICATION, f"{eid}: verification {ver!r}"
        src = sources[e["source_id"]]
        if ver in ("read_in_retrieved_text", "secondary_citation"):
            assert src.get("retrieved") is True, f"{eid}: claims to be read in a source that was not retrieved"
            assert e.get("locator"), f"{eid}: locator (page/table) required"
        if ver == "title_only_verify":
            assert e.get("verify") is True, f"{eid}: title-only values must carry verify=true"
        if ver == "repo_audit_record":
            assert src.get("repo_path"), f"{eid}: repo audit record needs a repo_path source"
        if ver == "derived_by_this_lane":
            assert e.get("quantity_type") in ("inferred", "model-derived"), eid
            deps = e.get("derived_from") or []
            assert deps and all(dep in entry_ids for dep in deps), f"{eid}: derived_from must list existing entries"
        if ver == "code_constant":
            assert e["source_id"] == "repo_code" and e.get("location"), eid
            if e.get("matches_entry"):
                assert e["matches_entry"] in entry_ids, eid
            else:
                assert e["evidence_level"] == 7 and e["quantity_type"] == "assumed", f"{eid}: unsourced constant"


def test_every_claim_has_source_and_evidence_class(dossier):
    sources = _sources(dossier)
    for c in _claims(dossier):
        cid = c.get("id", "<no id>")
        assert c.get("source_id") in sources, cid
        assert c.get("quantity_type") in QUANTITY_TYPES, cid
        assert isinstance(c.get("evidence_level"), int) and 1 <= c["evidence_level"] <= 7, cid
        assert c.get("verification") in VERIFICATION, cid
        assert c.get("locator"), cid


def test_no_bare_numbers_outside_entries(dossier):
    """A number anywhere in the JSON must be an entry value (checked above) or whitelisted metadata."""
    bad = []

    def walk(obj, key, in_value):
        if _is_number(obj):
            if not in_value and key not in NUMERIC_METADATA_KEYS:
                bad.append(key)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, k, k == "value")
        elif isinstance(obj, list):
            for v in obj:
                walk(v, key, in_value)

    walk(dossier, None, False)
    assert not bad, f"numbers outside entry values under keys: {sorted(set(map(str, bad)))}"


def test_no_vyovrinda_level_evidence_claimed(dossier):
    """No Vyovrinda cathode exists: levels 1-2 (in-house / identical hardware) must not appear."""
    for o in _entries(dossier) + _claims(dossier):
        if "evidence_level" in o:
            assert o["evidence_level"] >= 3, o.get("id")


def test_candidates_cover_every_parameter_category(dossier):
    cands = {c["id"]: c for c in dossier["candidates"]}
    assert REQUIRED_CANDIDATES <= set(cands)
    for cid, c in cands.items():
        params = c["parameters"]
        assert PARAMETER_CATEGORIES <= set(params), f"{cid}: missing {PARAMETER_CATEGORIES - set(params)}"
        for cat in PARAMETER_CATEGORIES:
            assert isinstance(params[cat], list) and params[cat], f"{cid}.{cat} must be a non-empty list"


def test_baseline_stays_xe_fed_and_air_fed_is_unresolved(dossier):
    b = dossier["baseline_decision"]
    assert "Xe-fed" in b["system_baseline_cathode"]
    assert b["atmospheric_gas_fed_cathode_operation"] == "UNRESOLVED"
    cands = {c["id"]: c for c in dossier["candidates"]}
    assert cands["air_fed_thermionic_hollow_cathode"]["status"] == "UNRESOLVED"
    for cid, c in cands.items():
        if c["status"].upper().startswith("BASELINE"):
            assert cid.startswith("xe_"), f"{cid}: only a Xe-fed cathode may be baseline"


def test_required_current_is_symbolic_not_invented(dossier):
    req = dossier["electron_current_requirement"]
    assert req["symbolic_relations"], "symbolic derivation missing"
    assert any("I_d = P_d / V_d" in r for r in req["symbolic_relations"])
    assert req["numeric_evaluation"]["value"] is None
    assert "TBD" in req["numeric_evaluation"]["tbd"]


def test_uncertainty_register_and_gaps_resolve(dossier):
    known = set(_all_ids(dossier))
    u_ids = {u["id"] for u in dossier["uncertainty_register"]}
    for u in dossier["uncertainty_register"]:
        assert u.get("description") and u.get("resolution"), u["id"]
        for ref in u.get("refs", []):
            assert ref in known, f"{u['id']}: unresolved ref {ref}"
    assert dossier["hardware_test_gaps"]
    for g in dossier["hardware_test_gaps"]:
        assert g.get("hardware_test"), g["id"]
        for ref in g.get("blocks", []):
            assert ref in u_ids, f"{g['id']}: unknown uncertainty {ref}"


def test_markdown_companion_exists(dossier):
    text = MD_PATH.read_text(encoding="utf-8")
    assert "cathode_evidence_v1.json" in text
    assert "UNRESOLVED" in text
    assert "Xe-fed" in text
    for g in dossier["hardware_test_gaps"]:
        assert g["id"] in text, f"gap {g['id']} missing from the dossier markdown"
