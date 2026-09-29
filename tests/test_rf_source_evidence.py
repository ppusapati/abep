"""RF ionization / pre-ionization source evidence audit (docs/evidence/rf_source/).

Checks the evidence matrix against its JSON schema, the evidence-discipline rules (every numeric entry has a
source, an evidence class and an access label; derived numbers reproduce from the committed script), and the
audit's scope guards (no ABEP regime claimed while the upstream ICD densities are TBD; no worth-its-power
verdict; no candidate-promotion language). Pure file checks: no network, no Julia, no simulator runs.
"""
from __future__ import annotations

import importlib.util
import json
import math
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
DIR = REPO / "docs" / "evidence" / "rf_source"
MATRIX_PATH = DIR / "rf_evidence_matrix.json"
SCHEMA_PATH = DIR / "rf_evidence_matrix.schema.json"
DOC_PATH = DIR / "RF_SOURCE_EVIDENCE.md"
DERIVE_PATH = DIR / "derive_rf_evidence.py"

EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
NUMERIC_KINDS = {"number", "range", "bound"}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def matrix():
    return _load(MATRIX_PATH)


@pytest.fixture(scope="module")
def schema():
    return _load(SCHEMA_PATH)


@pytest.fixture(scope="module")
def entries(matrix):
    return matrix["entries"]


# --------------------------------------------------------------------------- minimal JSON-Schema validator
# jsonschema is not a pinned dependency; this validator covers exactly the keywords the schema uses, and the
# test also runs jsonschema when it happens to be installed (no skip either way).
def _is_type(value, t):
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "null":
        return value is None
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    raise AssertionError(f"schema uses unsupported type {t!r}")


SUPPORTED = {"$schema", "$id", "title", "description", "$defs", "type", "required", "properties",
             "additionalProperties", "enum", "const", "pattern", "minLength", "minItems", "items", "$ref",
             "oneOf", "anyOf", "minimum", "maximum", "minProperties"}


def _validate(value, sch, root, path="$"):
    errs = []
    unknown = set(sch) - SUPPORTED
    assert not unknown, f"validator does not support schema keywords {unknown} at {path}"
    if "$ref" in sch:
        ref = sch["$ref"]
        assert ref.startswith("#/$defs/"), ref
        return _validate(value, root["$defs"][ref.split("/")[-1]], root, path)
    if "type" in sch:
        types = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_is_type(value, t) for t in types):
            return [f"{path}: expected type {types}, got {type(value).__name__}"]
    if "const" in sch and value != sch["const"]:
        errs.append(f"{path}: expected const {sch['const']!r}")
    if "enum" in sch and value not in sch["enum"]:
        errs.append(f"{path}: {value!r} not in enum {sch['enum']}")
    if isinstance(value, str):
        if len(value) < sch.get("minLength", 0):
            errs.append(f"{path}: shorter than {sch['minLength']}")
        if "pattern" in sch and not re.search(sch["pattern"], value):
            errs.append(f"{path}: {value!r} does not match {sch['pattern']}")
    if _is_type(value, "number"):
        if "minimum" in sch and value < sch["minimum"]:
            errs.append(f"{path}: {value} < minimum {sch['minimum']}")
        if "maximum" in sch and value > sch["maximum"]:
            errs.append(f"{path}: {value} > maximum {sch['maximum']}")
    if isinstance(value, list):
        if len(value) < sch.get("minItems", 0):
            errs.append(f"{path}: fewer than {sch['minItems']} items")
        if "items" in sch:
            for i, v in enumerate(value):
                errs.extend(_validate(v, sch["items"], root, f"{path}[{i}]"))
    if isinstance(value, dict):
        for k in sch.get("required", []):
            if k not in value:
                errs.append(f"{path}: missing required {k!r}")
        if len(value) < sch.get("minProperties", 0):
            errs.append(f"{path}: fewer than {sch['minProperties']} properties")
        props = sch.get("properties", {})
        for k, v in value.items():
            if k in props:
                errs.extend(_validate(v, props[k], root, f"{path}.{k}"))
            else:
                extra = sch.get("additionalProperties", True)
                if extra is False:
                    errs.append(f"{path}: additional property {k!r} not allowed")
                elif isinstance(extra, dict):
                    errs.extend(_validate(v, extra, root, f"{path}.{k}"))
    if "oneOf" in sch:
        n = sum(not _validate(value, s, root, path) for s in sch["oneOf"])
        if n != 1:
            errs.append(f"{path}: matches {n} of oneOf (need exactly 1)")
    if "anyOf" in sch:
        if not any(not _validate(value, s, root, path) for s in sch["anyOf"]):
            errs.append(f"{path}: matches none of anyOf")
    return errs


def test_schema_and_matrix_are_well_formed(matrix, schema):
    assert schema["$defs"]["entry"]["required"], "schema must define entry requirements"
    for field in ("id", "source", "evidence_class", "quantity", "value", "units", "uncertainty", "conditions",
                  "applicability_to_abep"):
        assert field in schema["$defs"]["entry"]["required"], field
    for field in ("citation", "doi_or_url", "access"):
        assert field in schema["$defs"]["source"]["required"], field
    assert set(schema["$defs"]["source"]["properties"]["access"]["enum"]) == {"open", "abstract_only"}
    assert set(schema["$defs"]["entry"]["properties"]["applicability_to_abep"]["properties"]["regime_match"]["enum"]) \
        == {"yes", "partial", "no", "TBD"}
    assert matrix["matrix_id"] == "rf_source_evidence_matrix"
    assert len(matrix["entries"]) >= 50


def test_document_validates_against_schema(matrix, schema):
    errs = _validate(matrix, schema, schema)
    assert not errs, "\n".join(errs[:40])


def test_every_entry_validates_against_entry_schema(entries, schema):
    entry_schema = schema["$defs"]["entry"]
    problems = {}
    for e in entries:
        errs = _validate(e, entry_schema, schema, e.get("id", "?"))
        if errs:
            problems[e.get("id", "?")] = errs
    assert not problems, json.dumps(problems, indent=1)[:4000]


def test_validator_rejects_malformed_entries(entries, schema):
    """Guard against a vacuous validator: typical defects must be caught."""
    import copy
    entry_schema = schema["$defs"]["entry"]
    good = next(e for e in entries if e["value_kind"] == "number")
    assert not _validate(good, entry_schema, schema)
    mutations = {
        "no access": lambda e: e["source"].pop("access"),
        "bad access": lambda e: e["source"].__setitem__("access", "paywalled"),
        "bad class": lambda e: e.__setitem__("evidence_class", "measured-ish"),
        "no uncertainty": lambda e: e.pop("uncertainty"),
        "extra field": lambda e: e.__setitem__("verdict", "x"),
        "bad regime": lambda e: e["applicability_to_abep"].__setitem__("regime_match", "maybe"),
        "no pressure/density key": lambda e: e["conditions"].pop("pressure_Pa"),
        "list value": lambda e: e.__setitem__("value", [1, 2]),
        "http url": lambda e: e["source"].__setitem__("doi_or_url", "http://example.org"),
    }
    for name, mutate in mutations.items():
        bad = copy.deepcopy(good)
        mutate(bad)
        bad["conditions"].pop("density_m3", None)
        assert _validate(bad, entry_schema, schema), f"validator missed: {name}"


def test_jsonschema_library_agrees_when_available(matrix, schema):
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        return  # optional cross-check only; the built-in validator above is authoritative in this repo
    jsonschema.validate(matrix, schema)


def test_ids_unique_and_source_urls_https(entries):
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
    for e in entries:
        assert e["source"]["doi_or_url"].startswith("https://"), e["id"]


def test_every_numeric_entry_has_source_and_evidence_class(entries):
    for e in entries:
        if e["value_kind"] not in NUMERIC_KINDS:
            continue
        s = e["source"]
        assert s["citation"].strip() and s["doi_or_url"].strip(), e["id"]
        assert s["access"] in ("open", "abstract_only"), e["id"]
        assert e["evidence_class"] in EVIDENCE_CLASSES, e["id"]
        assert isinstance(e["evidence_level"], int) and 1 <= e["evidence_level"] <= 7, e["id"]
        assert e["units"].strip() and e["units"] != "n/a", f"{e['id']}: numeric value needs units"
        assert e["uncertainty"].strip(), e["id"]
        assert e["locator"].strip(), f"{e['id']}: numeric value needs a locator in the source"


def test_no_entry_lacks_access_labelling(entries):
    for e in entries:
        access = e.get("source", {}).get("access")
        assert access in ("open", "abstract_only"), f"{e['id']}: access label missing/invalid"
        if access == "abstract_only":
            assert "abstract" in e["source"]["citation"].lower(), \
                f"{e['id']}: abstract-only access must be stated in the citation"
            assert e["value_kind"] in ("qualitative", "tbd"), \
                f"{e['id']}: no numbers are taken from abstract-only sources in v1"


def test_value_kind_matches_value(entries):
    for e in entries:
        v, k = e["value"], e["value_kind"]
        if k == "number":
            assert _is_type(v, "number"), e["id"]
        elif k == "range":
            assert isinstance(v, dict) and set(v) == {"min", "max"} and v["min"] <= v["max"], e["id"]
        elif k == "bound":
            assert isinstance(v, dict) and len(v) == 1 and set(v) <= {"min", "max"}, e["id"]
        elif k == "qualitative":
            assert isinstance(v, str) and len(v) >= 10, e["id"]
            assert e["evidence_class"] in EVIDENCE_CLASSES, e["id"]
        elif k == "tbd":
            assert v is None and e["evidence_class"] is None, e["id"]
            assert "not" in e["uncertainty"].lower(), f"{e['id']}: say why the quantity is TBD"
        # evidence_class may be null only for TBD entries
        if e["evidence_class"] is None:
            assert k == "tbd", e["id"]


def test_conditions_are_si_and_plausible(entries):
    def nums(x):
        if x is None:
            return []
        if isinstance(x, dict):
            return list(x.values())
        return [x]

    for e in entries:
        c = e["conditions"]
        for f in nums(c.get("frequency_Hz")):
            assert 1e3 <= f <= 1e10, f"{e['id']}: frequency_Hz {f} looks like a non-SI unit"
        for b in nums(c.get("B_T")):
            assert 0 <= b <= 5, f"{e['id']}: B_T {b} looks like a non-SI unit"
        for p in nums(c.get("pressure_Pa")):
            assert 0 <= p <= 1e6, e["id"]
        for w in nums(c.get("power_W")):
            assert 0 <= w <= 1e6, e["id"]


def _derive_module():
    spec = importlib.util.spec_from_file_location("derive_rf_evidence_for_test", DERIVE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_derived_numbers_reproduce_from_committed_script(matrix):
    mod = _derive_module()
    problems = mod.check(matrix)
    assert not problems, "\n".join(problems)
    derived = [e for e in matrix["entries"] if "derived" in e]
    assert derived, "expected derived entries"
    for e in derived:
        assert e["evidence_class"] == "inferred", f"{e['id']}: our arithmetic is 'inferred'"
        assert "derive_rf_evidence.py" in e["transformation_chain"], e["id"]
        assert e["derived"]["function"] in mod.FUNCTIONS, e["id"]


def test_derived_spot_values(matrix):
    by = {e["id"]: e for e in matrix["entries"]}
    # |Gamma|^2 at -6.0 dB
    assert abs(by["RF-IPT20-D1"]["value"] - 10 ** (-0.6)) < 1e-3
    # 10 Pa at 300 K
    assert abs(by["RF-SCHU24-D1"]["value"]["min"] - 10 / (1.380649e-23 * 300)) / 2.414e21 < 1e-3
    # eta_p from resistances brackets the source's 'about 90 %'
    rng = by["RF-TAKA22-D1"]["value"]
    assert rng["min"] < by["RF-TAKA22-01"]["value"] < rng["max"] + 0.01


def test_no_regime_yes_while_icd_densities_are_tbd(matrix):
    assert "TBD" in matrix["abep_side"] and "ICD" in matrix["abep_side"]
    offenders = [e["id"] for e in matrix["entries"] if e["applicability_to_abep"]["regime_match"] == "yes"]
    assert not offenders, (f"regime_match 'yes' needs the upstream ICD ionizer-inlet state, which is TBD: {offenders}. "
                           "Update this test only when the ICD exists.")


def test_every_topic_the_lane_requires_is_covered(entries):
    topics = {e["topic"] for e in entries}
    required = {"pressure_mode_limits", "power_coupling", "rf_generator_efficiency", "ion_production_cost",
                "ionization_fraction", "magnetic_field", "material_interaction", "thermal_load", "hardware_mass",
                "architecture_heritage"}
    assert required <= topics, required - topics


def test_markdown_report_structure_and_sources(entries):
    doc = DOC_PATH.read_text(encoding="utf-8")
    low = re.sub(r"\s+", " ", doc.replace("*", "")).lower()   # ignore markdown emphasis and line wrapping
    for heading in ("what must be measured", "regime-match", "source coverage", "not accessed",
                    "simulator priors"):
        assert heading in low, f"missing section: {heading}"
    for e in entries:
        assert e["source"]["doi_or_url"] in doc, f"{e['id']}: source {e['source']['doi_or_url']} not listed in the report"
    # scope guard: no verdict on whether RF pre-ionization is worth its power
    assert "no statement that rf pre-ionization is or is not worth its power" in low
    assert "common bus-power boundary" in low


def test_no_forbidden_language():
    forbidden = [r"best candidate", r"recommended candidate", r"\bpromot", r"would pass if", r"demonstrated abep closure",
                 r"architecture winner"]
    for path in (DOC_PATH, MATRIX_PATH):
        text = path.read_text(encoding="utf-8").lower()
        for pat in forbidden:
            assert not re.search(pat, text), f"{path.name}: forbidden phrase {pat!r}"
