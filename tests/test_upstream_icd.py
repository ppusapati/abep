"""Checks for the upstream gas-chain ICD (schemas/interfaces/upstream_icd_v1.json, docs/interfaces/UPSTREAM_ICD.md).

What is checked:
  * the schema parses, is versioned, uses only Draft 2020-12 keywords that the small validator below implements (plus
    annotations and x-* extensions), and every local $ref resolves;
  * every field carries a unit from the ICD unit vocabulary, and the schema enforces that unit on the record;
  * every interface covers all 13 variable classes (a field, or an explicit not-applicable reason);
  * status semantics: supplied/partial/derivable fields name existing code; gaps say "TBD - requires ...";
  * every producer/consumer that claims existing code resolves: the module imports, the attribute exists, and the
    output key appears in its source; repo files exist and contain the token;
  * closure independence: no field is named after (or produced by) a Hall transport closure, an ensemble member or a
    layer-1 calibration-nuisance variable, and the thruster-boundary records reject such fields;
  * the explanatory document names every interface and field.

jsonschema is not a project dependency, so a minimal validator for the keyword subset the ICD uses is implemented here
(the keyword test guarantees the schema stays inside that subset). No numeric data are used: the fixture record carries
null values only.
"""
from __future__ import annotations
import copy, importlib, inspect, json, os, re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(ROOT, "schemas", "interfaces", "upstream_icd_v1.json")
DOC_PATH = os.path.join(ROOT, "docs", "interfaces", "UPSTREAM_ICD.md")
ENSEMBLE_PATH = os.path.join(ROOT, "hallthruster_bridge", "ensemble", "transport_ensemble_v0.json")

EVIDENCE = ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"]
STATUSES = {"supplied", "partial", "derivable", "gap"}

# Draft 2020-12 keywords the ICD may use: those the validator below implements, plus pure annotations.
VALIDATING = {"$ref", "type", "properties", "additionalProperties", "required", "const", "enum", "items",
              "propertyNames", "anyOf"}
ANNOTATION = {"$schema", "$id", "$defs", "title", "description", "$comment"}


@pytest.fixture(scope="module")
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def _interfaces(s):
    return {k: s["$defs"][k] for k in s["x-icd"]["interface_order"]}


def _all_fields(s):
    """(section id, field name, property schema) for every interface field and every command."""
    out = []
    for iid, d in _interfaces(s).items():
        out += [(iid, n, p) for n, p in d["properties"].items()]
    out += [("commands", n, p) for n, p in s["$defs"]["commands"]["properties"].items()]
    return out


# ------------------------------------------------------------------------------------------ minimal validator
def _resolve(root, ref):
    assert ref.startswith("#/"), f"only local refs are allowed: {ref}"
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool}


def _is_type(v, t):
    if t == "null":
        return v is None
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


def validate(inst, sch, root, path="$"):
    """Errors of `inst` against `sch` for the keyword subset in VALIDATING (empty list = valid)."""
    errs = []
    if "$ref" in sch:
        errs += validate(inst, _resolve(root, sch["$ref"]), root, path)
    if "type" in sch:
        ts = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_is_type(inst, t) for t in ts):
            return errs + [f"{path}: type {type(inst).__name__} not in {ts}"]
    if "const" in sch and inst != sch["const"]:
        errs.append(f"{path}: {inst!r} != const {sch['const']!r}")
    if "enum" in sch and inst not in sch["enum"]:
        errs.append(f"{path}: {inst!r} not in enum")
    if "anyOf" in sch and not any(not validate(inst, sub, root, path) for sub in sch["anyOf"]):
        errs.append(f"{path}: matches no anyOf branch")
    if isinstance(inst, dict):
        for r in sch.get("required", []):
            if r not in inst:
                errs.append(f"{path}: missing required {r!r}")
        props = sch.get("properties", {})
        for k, v in inst.items():
            if "propertyNames" in sch:
                errs += validate(k, sch["propertyNames"], root, f"{path}.<{k}>")
            if k in props:
                errs += validate(v, props[k], root, f"{path}.{k}")
            elif "additionalProperties" in sch:
                ap = sch["additionalProperties"]
                if ap is False:
                    errs.append(f"{path}: additional property {k!r} not allowed")
                elif isinstance(ap, dict):
                    errs += validate(v, ap, root, f"{path}.{k}")
    if isinstance(inst, list) and "items" in sch:
        for i, v in enumerate(inst):
            errs += validate(v, sch["items"], root, f"{path}[{i}]")
    return errs


def _walk_schemas(node, visit, path="$"):
    """Visit every subschema (not property-name maps, not x-* annotations)."""
    visit(node, path)
    for k, v in node.items():
        if k.startswith("x-"):
            continue
        if k in ("properties", "$defs"):
            for name, sub in v.items():
                _walk_schemas(sub, visit, f"{path}.{k}.{name}")
        elif k in ("additionalProperties", "items", "propertyNames") and isinstance(v, dict):
            _walk_schemas(v, visit, f"{path}.{k}")
        elif k == "anyOf":
            for i, sub in enumerate(v):
                _walk_schemas(sub, visit, f"{path}.anyOf[{i}]")


def _null_record(s):
    """A schema-shaped record with every value null (test fixture; no numbers)."""
    unc = {"kind": "TBD", "basis": "fixture"}
    shapes = {
        "#/$defs/scalar_quantity": lambda u: {"value": None, "unit": u, "evidence_class": "TBD", "uncertainty": unc},
        "#/$defs/species_quantity": lambda u: {"values": {"O": None, "N2": None, "O2": None}, "unit": u,
                                               "evidence_class": "TBD", "uncertainty": unc},
        "#/$defs/flag": lambda u: {"value": None, "unit": u, "source": "fixture"},
        "#/$defs/label": lambda u: {"value": None, "unit": u, "source": "fixture"},
    }
    rec = {"icd": "upstream_icd", "icd_version": s["x-icd"]["version"],
           "record_provenance": {"producer": "tests/test_upstream_icd.py", "git_commit": "fixture"},
           "interfaces": {}, "commands": {}}
    for iid, d in _interfaces(s).items():
        rec["interfaces"][iid] = {n: shapes[p["$ref"]](p["x-field"]["unit"]) for n, p in d["properties"].items()}
    for n, p in s["$defs"]["commands"]["properties"].items():
        rec["commands"][n] = shapes[p["$ref"]](p["x-field"]["unit"])
    return rec


# ------------------------------------------------------------------------------------------ structure
def test_schema_parses_and_is_versioned(schema):
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("upstream_icd_v1")
    v = schema["x-icd"]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", v)
    assert v.split(".")[0] == "1", "file name upstream_icd_v1 must match the major version"
    assert schema["properties"]["icd_version"]["const"] == v
    assert schema["properties"]["icd"]["const"] == schema["x-icd"]["name"] == "upstream_icd"


def test_schema_uses_only_known_keywords(schema):
    bad = []

    def visit(node, path):
        for k in node:
            if not (k in VALIDATING or k in ANNOTATION or k.startswith("x-")):
                bad.append(f"{path}: {k}")
    _walk_schemas(schema, visit)
    assert not bad, bad


def test_all_refs_resolve(schema):
    refs = []
    _walk_schemas(schema, lambda node, path: refs.append(node["$ref"]) if "$ref" in node else None)
    assert refs
    for r in refs:
        _resolve(schema, r)


def test_interface_order_matches_definitions(schema):
    order = schema["x-icd"]["interface_order"]
    assert list(schema["properties"]["interfaces"]["properties"]) == order
    assert schema["properties"]["interfaces"]["additionalProperties"] is False
    for iid in order:
        d = schema["$defs"][iid]
        assert d["x-interface"]["id"] == iid
        assert d["additionalProperties"] is False, f"{iid} must be closed (no undeclared fields)"
        assert d["x-interface"]["path"] in ("atmospheric", "xenon")
    assert set(schema["x-icd"]["thruster_boundary"]) == {i for i in order if schema["$defs"][i]["x-interface"]["thruster_boundary"]}


def test_species_match_constants(schema):
    from abep_sim.constants import M_SPECIES
    assert set(schema["x-icd"]["species"]) == set(M_SPECIES)
    assert set(schema["$defs"]["species"]["enum"]) == set(M_SPECIES)


# ------------------------------------------------------------------------------------------ units
def test_every_field_has_a_unit_that_the_schema_enforces(schema):
    vocab = schema["x-icd"]["units"]
    fields = _all_fields(schema)
    assert len(fields) > 100
    for sec, name, p in fields:
        u = p["x-field"].get("unit")
        assert isinstance(u, str) and u, f"{sec}.{name}: no unit"
        assert u in vocab, f"{sec}.{name}: unit {u!r} not in x-icd.units"
        assert p["properties"]["unit"]["const"] == u, f"{sec}.{name}: enforced unit differs from x-field.unit"
        assert "unit" in _resolve(schema, p["$ref"])["required"], f"{sec}.{name}: record may omit its unit"


def test_record_with_wrong_unit_is_rejected(schema):
    rec = _null_record(schema)
    assert validate(rec, schema, schema) == []
    bad = copy.deepcopy(rec)
    bad["interfaces"]["IF-A4"]["p_total_Pa"]["unit"] = "Torr"
    assert any("const" in e for e in validate(bad, schema, schema))
    bad = copy.deepcopy(rec)
    del bad["interfaces"]["IF-A3"]["mdot_s_kgps"]["unit"]
    assert any("unit" in e for e in validate(bad, schema, schema))


def test_non_null_value_needs_an_evidence_class(schema):
    rec = _null_record(schema)
    q = rec["interfaces"]["IF-A0"]["rho_kgpm3"]
    q["value"] = 1.0                      # structural fixture value, not data
    assert validate(rec, schema, schema) != []           # evidence_class still 'TBD'
    q["evidence_class"] = "model-derived"
    assert validate(rec, schema, schema) == []


# ------------------------------------------------------------------------------------------ coverage and status
def test_every_interface_covers_every_variable_class(schema):
    classes = set(schema["x-icd"]["variable_classes"])
    assert len(classes) == 13
    for iid, d in _interfaces(schema).items():
        covered = {p["x-field"]["variable_class"] for p in d["properties"].values()}
        na = d["x-interface"]["not_applicable"]
        assert covered <= classes, (iid, covered - classes)
        assert not covered & set(na), (iid, covered & set(na))
        assert covered | set(na) == classes, (iid, classes - covered - set(na))
        assert all(isinstance(r, str) and r for r in na.values()), iid
    for n, p in schema["$defs"]["commands"]["properties"].items():
        assert p["x-field"]["variable_class"] == "command", n


def test_field_annotations_are_complete(schema):
    domains = schema["x-icd"]["validity_domains"]
    for sec, name, p in _all_fields(schema):
        xf = p["x-field"]
        where = f"{sec}.{name}"
        assert xf["status"] in STATUSES, where
        assert xf["definition"], where
        assert xf["validity_domain"] in domains, where
        assert xf["evidence_class_current"] in EVIDENCE + ["TBD"], where
        assert isinstance(xf["uncertainty"], str) and xf["uncertainty"], where
        assert xf["producers"] and xf["consumers"], where
        real = [q for q in xf["producers"] if q["kind"] != "TBD"]
        if xf["status"] == "gap":
            assert not real, f"{where}: a gap names a producer"
            assert xf["requires"].startswith("TBD"), where
            assert xf["evidence_class_current"] == "TBD", where
            assert xf["validity_domain"] == "D-TBD", where
        else:
            assert real, f"{where}: status {xf['status']} without an existing producer"
            assert xf["evidence_class_current"] in EVIDENCE, where
        if xf["status"] == "derivable":
            assert xf.get("derivation"), f"{where}: derivable without a derivation"
        if xf["status"] == "partial":
            assert xf.get("requires", "").startswith("TBD") or xf.get("note"), f"{where}: partial without what is missing"
        for q in xf["producers"] + xf["consumers"]:
            assert q["kind"] in ("python", "repo_file", "external", "TBD"), where
            if q["kind"] == "TBD":
                assert q["requires"], where


def _source_of(obj):
    try:
        return inspect.getsource(obj)
    except (TypeError, OSError):
        return None


# A9.22 Phase B (owner decision A9.22 items 6-7; docs/decisions/OD_2026_10_03_A9_22_*): abep_sim.system.evaluate is
# now the pre-split compatibility merge legacy_merge(physics_closure(cfg), assess(...)); the gas-path quantities the
# ICD names are produced / consumed inside the raw producer abep_sim.system.physics_closure. The ICD v1 files keep
# naming the public entry point `evaluate` (their sha256 is pinned by byte-reproduced records, e.g. H2-3 v1 and
# subsystem maturity v1/v2, so they are not rewritten); an ICD reference to a delegating entry point resolves to its
# raw producer ONLY when the delegation is demonstrated behaviourally (test_evaluate_delegates_to_raw_producer).
RAW_PRODUCER_OF = {("abep_sim.system", "evaluate"): "physics_closure"}


def _check_python_ref(q, where):
    mod = importlib.import_module(q["module"])
    obj = mod
    for part in q["attribute"].split("."):
        assert hasattr(obj, part), f"{where}: {q['module']}.{q['attribute']} does not exist"
        obj = getattr(obj, part)
    key = q.get("output_key")
    if key is None:
        return
    holders = [q.get("key_source", q["attribute"])]
    if "key_source" not in q and (q["module"], q["attribute"]) in RAW_PRODUCER_OF:
        holders.append(RAW_PRODUCER_OF[(q["module"], q["attribute"])])
    found = False
    for name in holders:
        holder = mod
        for part in name.split("."):
            holder = getattr(holder, part)
        src = _source_of(holder)
        assert src is not None, f"{where}: cannot read the source of {q['module']}.{name}"
        found = found or bool(re.search(rf"\b{re.escape(key)}\b", src))
    assert found, f"{where}: key {key!r} not found in {q['module']}.{' / '.join(holders)}"


def test_evaluate_delegates_to_raw_producer(monkeypatch):
    """Behaviour behind RAW_PRODUCER_OF: evaluate() obtains its raw quantities from physics_closure() (it calls it once
    with the same config, and every raw key physics_closure returns, except the raw-only bookkeeping keys, reaches the
    evaluate() record with the identical value). Fails closed if evaluate stops delegating."""
    import abep_sim.system as S
    from abep_sim.assessment.closure_checks import RAW_ONLY_KEYS
    assert set(RAW_PRODUCER_OF) == {("abep_sim.system", "evaluate")}
    cfg = S.Config(architecture="hall_1stage")
    raw = S.physics_closure(cfg)
    real, calls = S.physics_closure, []

    def spy(c):
        calls.append(c)
        return real(c)

    monkeypatch.setattr(S, "physics_closure", spy)
    out = S.evaluate(cfg)
    assert calls == [cfg]
    passed = [k for k in raw if k not in RAW_ONLY_KEYS]
    assert "atm_source" in passed and "mdot_air_mgps" in passed
    for k in passed:
        assert k in out and (out[k] == raw[k] or (out[k] != out[k] and raw[k] != raw[k])), k


def test_existing_code_references_resolve(schema):
    n = 0
    for sec, name, p in _all_fields(schema):
        for q in p["x-field"]["producers"] + p["x-field"]["consumers"]:
            where = f"{sec}.{name}"
            if q["kind"] == "python":
                _check_python_ref(q, where); n += 1
            elif q["kind"] == "repo_file":
                fp = os.path.join(ROOT, q["file"])
                assert os.path.isfile(fp), f"{where}: {q['file']} missing"
                with open(fp) as f:
                    assert q["token"] in f.read(), f"{where}: {q['token']!r} not in {q['file']}"
                n += 1
    assert n > 150


def test_supplied_fields_point_at_upstream_code(schema):
    """A supplied upstream value comes from abep_sim gas-path/system code, never from the Hall bridge or Hall modules."""
    prefixes = schema["x-icd"]["closure_independence"]["forbidden_producer_prefixes"]
    for sec, name, p in _all_fields(schema):
        for q in p["x-field"]["producers"]:
            ident = q.get("module") or q.get("file") or ""
            assert not any(ident.startswith(pre) for pre in prefixes), f"{sec}.{name}: produced by {ident}"


# ------------------------------------------------------------------------------------------ closure independence
def test_calibration_nuisance_never_appears_upstream(schema):
    with open(ENSEMBLE_PATH) as f:
        nuisance = set(json.load(f)["calibration_nuisance"])
    ci = schema["x-icd"]["closure_independence"]
    forbidden = set(ci["identifiers"])
    assert nuisance <= forbidden, f"calibration-nuisance keys missing from the forbidden list: {nuisance - forbidden}"
    assert "ensemble_member_id" in forbidden
    names = [(sec, name) for sec, name, _ in _all_fields(schema)]
    names += [(k, k) for k in schema["properties"]]
    for sec, name in names:
        for fid in forbidden:
            assert fid.lower() not in name.lower(), f"{sec}.{name} contains forbidden identifier {fid!r}"


def test_thruster_boundary_rejects_closure_and_nuisance_fields(schema):
    with open(ENSEMBLE_PATH) as f:
        nuisance = list(json.load(f)["calibration_nuisance"])
    rec = _null_record(schema)
    assert validate(rec, schema, schema) == []
    for iid in schema["x-icd"]["thruster_boundary"]:
        for key in ["ensemble_member_id", "transport", *nuisance]:
            bad = copy.deepcopy(rec)
            bad["interfaces"][iid][key] = {"value": None, "unit": "-", "source": "fixture"}
            assert any("not allowed" in e for e in validate(bad, schema, schema)), (iid, key)
    for key in ["ensemble_member_id", *nuisance]:            # nor on the record as a whole
        bad = copy.deepcopy(rec)
        bad[key] = "x"
        assert any("not allowed" in e for e in validate(bad, schema, schema)), key


# ------------------------------------------------------------------------------------------ document
def test_document_names_every_interface_and_field(schema):
    with open(DOC_PATH) as f:
        doc = f.read()
    for iid in schema["x-icd"]["interface_order"]:
        assert iid in doc, iid
    for sec, name, _ in _all_fields(schema):
        assert f"`{name}`" in doc, f"{sec}.{name} not documented"
    assert "upstream_icd_v1.json" in doc and "never leak" in doc.lower()
