"""H-1 magnet/coil qualification basis (docs/experiments/magnet_coil/): schema, sourcing, discipline, recomputation.

- the JSON validates against its JSON Schema (small draft-2020-12 subset validator, no third-party dependency);
- the committed JSON is exactly what the builder produces (every computed value comes from a committed script);
- every value record carries a known source, a locator, an evidence level and a quantity type; TBDs are explicit;
- no candidate carries a lifetime verdict; MMPA / EEE-INST-002 are reference-only and never a candidate value source;
- requirements and thresholds are PROPOSED; every cross-referenced MCQ id exists;
- derived values are recomputed here with independently written formulas;
- repository references that claim to be in the base exist; nothing depends on sibling worktrees;
- the markdown names only ids that exist and lists every requirement id.
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "experiments" / "magnet_coil"
DATA = DIR / "magnet_coil_qualification_v1.json"
SCHEMA = DIR / "magnet_coil_qualification_v1.schema.json"
MD = DIR / "MAGNET_COIL_QUALIFICATION.md"
BUILDER = DIR / "build_magnet_coil_qualification.py"

CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
ARCH_IDS = ("hall_only", "rf_hall", "ecr_hall")


@pytest.fixture(scope="module")
def doc():
    return json.loads(DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------ minimal JSON Schema validator
def _type_ok(inst, t):
    if isinstance(t, list):
        return any(_type_ok(inst, x) for x in t)
    return {
        "null": inst is None,
        "boolean": isinstance(inst, bool),
        "object": isinstance(inst, dict),
        "array": isinstance(inst, list),
        "string": isinstance(inst, str),
        "number": isinstance(inst, (int, float)) and not isinstance(inst, bool),
        "integer": isinstance(inst, int) and not isinstance(inst, bool),
    }[t]


def _ref(ref, root):
    assert ref.startswith("#/"), ref
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(inst, sch, root, path="$"):
    if "$ref" in sch:
        validate(inst, _ref(sch["$ref"], root), root, path)
    if "anyOf" in sch:
        errs = []
        for sub in sch["anyOf"]:
            try:
                validate(inst, sub, root, path)
                break
            except AssertionError as e:  # try next branch
                errs.append(str(e))
        else:
            raise AssertionError(f"{path}: no anyOf branch matched: {errs}")
    if "type" in sch:
        assert _type_ok(inst, sch["type"]), f"{path}: expected {sch['type']}, got {type(inst).__name__}"
    if "const" in sch:
        assert inst == sch["const"], f"{path}: {inst!r} != const {sch['const']!r}"
    if "enum" in sch:
        assert inst in sch["enum"], f"{path}: {inst!r} not in {sch['enum']}"
    if isinstance(inst, str):
        if "pattern" in sch:
            assert re.search(sch["pattern"], inst), f"{path}: {inst!r} !~ {sch['pattern']}"
        if "minLength" in sch:
            assert len(inst) >= sch["minLength"], f"{path}: too short"
    if _type_ok(inst, "number"):
        if "minimum" in sch:
            assert inst >= sch["minimum"], f"{path}: below minimum"
        if "maximum" in sch:
            assert inst <= sch["maximum"], f"{path}: above maximum"
    if isinstance(inst, dict):
        for k in sch.get("required", []):
            assert k in inst, f"{path}: missing required {k!r}"
        props = sch.get("properties", {})
        for k, v in inst.items():
            if k in props:
                validate(v, props[k], root, f"{path}.{k}")
            else:
                ap = sch.get("additionalProperties", True)
                if ap is False:
                    raise AssertionError(f"{path}: additional property {k!r}")
                if isinstance(ap, dict):
                    validate(v, ap, root, f"{path}.{k}")
    if isinstance(inst, list):
        if "minItems" in sch:
            assert len(inst) >= sch["minItems"], f"{path}: fewer than {sch['minItems']} items"
        if "items" in sch:
            for i, v in enumerate(inst):
                validate(v, sch["items"], root, f"{path}[{i}]")


def test_schema_validates(doc, schema):
    validate(doc, schema, schema)


def test_schema_rejects_a_lifetime_verdict(doc, schema):
    bad = json.loads(json.dumps(doc))
    bad["candidates"][0]["lifetime_verdict"] = "PASS"
    with pytest.raises(AssertionError):
        validate(bad, schema, schema)


def test_schema_rejects_an_unsourced_value(doc, schema):
    bad = json.loads(json.dumps(doc))
    rec = next(iter(bad["candidates"][0]["values"].values()))
    del rec["source_id"]
    with pytest.raises(AssertionError):
        validate(bad, schema, schema)


# -------------------------------------------------------------------------------------------- builder
def _load_builder():
    spec = importlib.util.spec_from_file_location("build_magnet_coil_qualification", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_committed_json_is_builder_output():
    mod = _load_builder()
    assert mod.render(mod.build()) == DATA.read_text(encoding="utf-8"), "rerun the builder"


# ------------------------------------------------------------------------------------------ sourcing
def _value_records(doc):
    for c in doc["candidates"]:
        for name, rec in c["values"].items():
            yield c["id"], name, rec
    for rec in doc["h1_requirement_basis"]["B_magnitude_class"]["evidence"]:
        yield "h1_basis", "B_class", rec


def test_every_value_is_sourced_or_explicit_tbd(doc):
    n = 0
    for cid, name, rec in _value_records(doc):
        if rec.get("value") is None:
            assert rec.get("TBD", "").startswith("TBD - requires "), (cid, name)
            continue
        n += 1
        src = rec["source_id"]
        if src.startswith("repo:"):
            assert (ROOT / src[len("repo:"):]).exists(), (cid, name, src)
        else:
            assert src in doc["sources"], (cid, name, src)
        assert rec["quantity_type"] in CLASSES
        assert 1 <= rec["evidence_level"] <= 7
        for key in ("locator", "as_published", "uncertainty", "applicability_domain", "validation_status"):
            assert rec[key].strip(), (cid, name, key)
    assert n > 30


def test_sources_have_hash_and_open_url(doc):
    for sid, s in doc["sources"].items():
        assert re.fullmatch(r"[0-9a-f]{64}", s["sha256_accessed"]), sid
        assert s["url"].startswith("https://"), sid
    for qt in doc["qualification_tests"]:
        for sid in qt["source_ids"]:
            assert sid in doc["sources"], (qt["id"], sid)
    # every declared source is actually used somewhere (no decorative citations)
    text = json.dumps({k: v for k, v in doc.items() if k != "sources"})
    for sid in doc["sources"]:
        assert sid in text, f"source {sid} declared but never used"


def test_reference_only_sources_never_feed_candidate_values(doc):
    refs = {r["id"]: r for r in doc["reference_only_evidence"]}
    assert all(r["never_produces_lifetime_verdict"] is True for r in refs.values())
    for cid, name, rec in _value_records(doc):
        if rec.get("value") is None:
            continue
        assert rec["source_id"] not in ("mmpa_0100_00",), (cid, name)
        assert "eee_inst_002" not in rec["source_id"], (cid, name)
        assert "mmpa" not in rec.get("locator", "").lower() or cid == "h1_basis", (cid, name)
    for r in refs.values():
        for sid in r["source_ids"]:
            assert sid in doc["sources"] or (ROOT / sid[len("repo:"):]).exists(), (r["id"], sid)
    whats = " ".join(r["what"] for r in refs.values())
    assert "EEE-INST-002" in whats and "MMPA" in whats


def test_no_verdicts_and_statuses_are_draft(doc):
    assert doc["status"] == "DRAFT_FOR_OWNER_REVIEW"
    for c in doc["candidates"]:
        assert c["lifetime_verdict"] is None
        assert c["status"] in ("CANDIDATE", "CANDIDATE_INCOMPLETE_DATA", "NOT_SOURCED_FOR_SELECTION")
    for r in doc["requirements"]:
        assert r["status"] == "PROPOSED"
    for t in doc["proposed_thresholds"]:
        assert t["status"] == "PROPOSED"
    assert all(s["state"] == "MISSING" for s in doc["s1_gate_items"])


def test_no_screening_candidates_or_p5_design_values(doc):
    text = json.dumps(doc)
    assert "sgb-screen" not in text
    for cid, name, rec in _value_records(doc):
        src = rec.get("source_id", "")
        assert "hallthruster_bridge" not in src, (cid, name)
        assert "p5" not in src.lower(), (cid, name)
    assert "never design values" in doc["h1_requirement_basis"]["B_magnitude_class"]["forbidden_sources"]


def test_milestones_stated(doc):
    m = doc["milestones"]
    assert set(m["supports"]) <= {"A", "B", "C"} and m["supports"]
    for k in ("A", "B", "C"):
        assert len(m[k]) > 40
    assert m["to_reach_next"]
    for arch in ARCH_IDS:
        assert arch in m["A"]


# --------------------------------------------------------------------------------------- cross refs
def _ids(doc):
    ids = set()
    for key in ("candidates", "reference_only_evidence", "qualification_tests", "requirements",
                "proposed_thresholds", "lane15_answers", "s1_gate_items", "open_owner_questions", "derived"):
        for item in doc[key]:
            assert item["id"] not in ids, f"duplicate id {item['id']}"
            ids.add(item["id"])
    return ids


def test_cross_references_resolve(doc):
    ids = _ids(doc)
    for c in doc["candidates"]:
        for qt in c["qualification_tests"]:
            assert qt in ids, (c["id"], qt)
    for s in doc["s1_gate_items"]:
        for r in s["requirements"]:
            assert r in ids, (s["id"], r)
    text = json.dumps(doc)
    for ref in set(re.findall(r"MCQ-(?:QT|W3|W4|TL|AO|PT|L15|S1|OQ|REF|PM|EM|EIS)-\d{2}", text)):
        assert ref in ids, f"dangling reference {ref}"


def test_every_candidate_has_the_core_tests(doc):
    for c in doc["candidates"]:
        qts = set(c["qualification_tests"])
        assert "MCQ-QT-03" in qts, c["id"]  # vacuum bake / outgassing for everything
        if c["kind"] == "permanent_magnet":
            assert {"MCQ-QT-02", "MCQ-QT-04", "MCQ-QT-09"} <= qts, c["id"]
        else:
            assert {"MCQ-QT-01", "MCQ-QT-06"} <= qts, c["id"]


def test_repository_references_exist(doc):
    for ref in doc["repository_references"]:
        assert ref["present_in_base"] is True
        assert (ROOT / ref["path"]).exists(), ref["path"]
    for p in doc["planned_paths_referenced_only"]:
        assert ".claude/worktrees" not in p["path"]


# ------------------------------------------------------------------------------------------- derived
def _d(doc, did):
    return next(x for x in doc["derived"] if x["id"] == did)


def test_derived_unit_conversions_and_ratios(doc):
    for did, f in (("MCQ-D-01-continuous_max", 1000.0), ("MCQ-D-01-continuous_min", -450.0),
                   ("MCQ-D-01-short_term_max", 1500.0), ("MCQ-D-01-nickel_migration_onset", 600.0)):
        assert _d(doc, did)["value"] == pytest.approx((f - 32.0) / 1.8, abs=0.006)
    assert _d(doc, "MCQ-D-02-500F")["value"] == pytest.approx(138.0 / 26.9, abs=6e-4)
    assert _d(doc, "MCQ-D-02-1000F")["value"] == pytest.approx(228.0 / 42.3, abs=6e-4)


def test_derived_reversible_factors(doc):
    cases = {"Recoma_33E": (-0.035, -0.25, 200.0, 1750.0), "N35EH": (-0.12, -0.47, 200.0, 2388.0),
             "N42SH": (-0.12, -0.55, 150.0, 1592.0)}
    for slug, (a, b, t, h) in cases.items():
        assert _d(doc, f"MCQ-D-03-{slug}")["value"] == pytest.approx(1 + a * (t - 20) / 100, abs=6e-5)
        assert _d(doc, f"MCQ-D-04-{slug}")["value"] == pytest.approx(h * (1 + b * (t - 20) / 100), abs=0.06)
        assert "NOT a knee field" in _d(doc, f"MCQ-D-04-{slug}")["note"]


def test_derived_reference_temperatures_and_ecr_ratio(doc):
    d5 = _d(doc, "MCQ-D-05")
    temps = [r["T_C"] for r in d5["inputs"]["readings"]]
    assert d5["value"]["min_C"] == min(temps) == 374.8
    assert d5["value"]["max_C"] == max(temps) == 535.6
    assert d5["evidence_level"] == 6 and "REFERENCE ONLY" in d5["note"]
    b_res = 2 * math.pi * 2.45e9 * 9.1093837139e-31 / 1.602176634e-19
    assert b_res == pytest.approx(0.08752, abs=1e-5)  # lane 20 EM-RESONANCE-B
    assert _d(doc, "MCQ-D-06-EV-B2_150G")["value"] == pytest.approx(b_res / 0.015, abs=0.006)
    assert _d(doc, "MCQ-D-06-EV-B4_200G")["value"] == pytest.approx(b_res / 0.02, abs=0.006)


def test_transcriptions_match_lane15_records_where_shared(doc):
    limits = json.loads((ROOT / "schemas" / "thermal_life" / "limits_v1.json").read_text(encoding="utf-8"))
    r35 = limits["records"]["pm_sm2co17_recoma35e"]["values"]["T_max_use_C"]["value"]
    pm02 = next(c for c in doc["candidates"] if c["id"] == "MCQ-PM-02")
    assert pm02["values"]["max_operating_T_summary_table"]["value"] == r35
    n42 = limits["records"]["pm_ndfeb_n42sh_arnold"]["values"]
    pm05 = next(c for c in doc["candidates"] if c["id"] == "MCQ-PM-05")
    assert pm05["values"]["alpha_HcJ_catalog"]["value"] == pytest.approx(n42["beta_Hcj_pct_per_C"]["value"], abs=0.0015)
    # the MMPA NdFeB value stays gated in lane 15 and is not un-gated here
    assert limits["records"]["pm_ndfeb_mmpa"]["values"]["T_max_use_C"]["value"] is None
    ans = {a["id"]: a for a in doc["lane15_answers"]}
    assert ans["MCQ-L15-02"]["status"] == "REMAINS_TBD"


# ------------------------------------------------------------------------------------------ markdown
def test_markdown_consistent(doc):
    md = MD.read_text(encoding="utf-8")
    ids = _ids(doc)
    for ref in set(re.findall(r"MCQ-(?:QT|W3|W4|TL|AO|PT|L15|S1|OQ|REF|PM|EM|EIS|D)-\d{2}", md)):
        assert ref in ids or any(i.startswith(ref) for i in ids), f"markdown names unknown id {ref}"
    for r in doc["requirements"]:
        assert r["id"] in md, r["id"]
    for q in doc["qualification_tests"]:
        assert q["id"] in md, q["id"]
    for arch in ARCH_IDS:
        assert f"`{arch}`" in md
    assert "DRAFT" in md and "PROPOSED" in md and "reference evidence only" in md
    low = md.lower()
    assert "no architecture winner is declared" in low
    for bad in ("is qualified for", "recommended winner", "we select"):
        assert bad not in low
