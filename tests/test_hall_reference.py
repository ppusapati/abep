"""Common Hall accelerator reference (hall_reference_v1): schema, evidence discipline and contract consistency.

Checks docs/architecture_comparison/hall_reference/hall_reference_v1.json against
schemas/architecture_comparison/hall_reference_v1.schema.json with a minimal validator (jsonschema is not in
requirements-lock.txt), and checks that:
  - the wall/life field names exist in hallthruster_bridge/hall_map_schema_v1.json (and abep_sim.hall_map.REQUIRED_FIELDS);
  - every JSON number is inside a SOURCED / PROPOSED / OWNER_DECIDED quantity, and every TBD quantity is null;
  - the invariance rules cover geometry, B(z), the voltage set and the cathode, field by field;
  - no P5/ECHT file is a design-value source, and no screening candidate is a transport source;
  - the discharge-voltage range is the span of the span-defining points under rule VR-1, and every other literature
    point (incl. the Dukhopelnikov sweep and the MCFT-2139) stays on record with an exclusion reason;
  - the ideal-beam table (incl. jet power at the RFP thrust ends) equals the output of its committed generator script;
  - the envelope tie uses measured (thrust, discharge power) pairs, whose derived numbers equal the generator's output,
    and never applies an anodic efficiency to the ideal-beam jet power;
  - provisional other-lane mappings and the 0.0 V solver coupling placeholder are labelled as such.
Other lanes' contracts (bus boundary, harness, ICD, Hall-map spec, evidence matrices) are referenced by path only and
are NOT required to exist.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_DIR = os.path.join(ROOT, "docs", "architecture_comparison", "hall_reference")
REF_FILE = os.path.join(REF_DIR, "hall_reference_v1.json")
DOC_FILE = os.path.join(REF_DIR, "HALL_ACCELERATOR_REFERENCE.md")
SCRIPT_FILE = os.path.join(REF_DIR, "voltage_envelope.py")
SCHEMA_FILE = os.path.join(ROOT, "schemas", "architecture_comparison", "hall_reference_v1.schema.json")
HALL_MAP_SCHEMA_FILE = os.path.join(ROOT, "hallthruster_bridge", "hall_map_schema_v1.json")

ARCHITECTURES = {"hall_only", "rf_hall", "ecr_hall"}
BUS_COMPONENTS = {"hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control", "compressor",
                  "thermal_control", "housekeeping", "rf_source", "ecr_source", "ecr_magnet"}
EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
VALUED_STATUSES = {"SOURCED", "PROPOSED", "OWNER_DECIDED"}
P5_ECHT_SOURCE_IDS = {"SRC-P5N2-CASES", "SRC-ECHT-AUDIT", "SRC-ECHT-TABLES"}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def ref():
    return _load(REF_FILE)


@pytest.fixture(scope="module")
def schema():
    return _load(SCHEMA_FILE)


# ----------------------------------------------------------------------------------------------- minimal validator
SUPPORTED_KEYWORDS = {"type", "enum", "const", "properties", "required", "additionalProperties", "items", "minItems",
                      "maxItems", "uniqueItems", "minLength", "pattern", "$ref", "anyOf", "allOf", "minProperties"}
ANNOTATIONS = {"$schema", "$id", "title", "description", "$defs"}
_TYPES = {
    "object": lambda x: isinstance(x, dict),
    "array": lambda x: isinstance(x, list),
    "string": lambda x: isinstance(x, str),
    "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
    "boolean": lambda x: isinstance(x, bool),
    "null": lambda x: x is None,
}


def _resolve_ref(root, ref_str):
    assert ref_str.startswith("#/"), f"only local $ref supported: {ref_str}"
    node = root
    for part in ref_str[2:].split("/"):
        node = node[part]
    return node


def validate(instance, sch, root, path="$"):
    """Return a list of error strings (empty = valid) for the keywords in SUPPORTED_KEYWORDS."""
    errs = []
    if "$ref" in sch:
        errs += validate(instance, _resolve_ref(root, sch["$ref"]), root, path)
    if "type" in sch:
        types = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_TYPES[t](instance) for t in types):
            return errs + [f"{path}: type {type(instance).__name__} not in {types}"]
    if "enum" in sch and instance not in sch["enum"]:
        errs.append(f"{path}: {instance!r} not in enum {sch['enum']}")
    if "const" in sch and instance != sch["const"]:
        errs.append(f"{path}: {instance!r} != const {sch['const']!r}")
    if isinstance(instance, str):
        if "minLength" in sch and len(instance) < sch["minLength"]:
            errs.append(f"{path}: shorter than {sch['minLength']}")
        if "pattern" in sch and not re.search(sch["pattern"], instance):
            errs.append(f"{path}: {instance!r} does not match {sch['pattern']!r}")
    if isinstance(instance, list):
        if "minItems" in sch and len(instance) < sch["minItems"]:
            errs.append(f"{path}: fewer than {sch['minItems']} items")
        if "maxItems" in sch and len(instance) > sch["maxItems"]:
            errs.append(f"{path}: more than {sch['maxItems']} items")
        if sch.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in instance}) != len(instance):
            errs.append(f"{path}: items not unique")
        if "items" in sch:
            for i, x in enumerate(instance):
                errs += validate(x, sch["items"], root, f"{path}[{i}]")
    if isinstance(instance, dict):
        props = sch.get("properties", {})
        for k in sch.get("required", []):
            if k not in instance:
                errs.append(f"{path}: missing required {k!r}")
        if "minProperties" in sch and len(instance) < sch["minProperties"]:
            errs.append(f"{path}: fewer than {sch['minProperties']} properties")
        for k, v in instance.items():
            if k in props:
                errs += validate(v, props[k], root, f"{path}.{k}")
            elif "additionalProperties" in sch:
                ap = sch["additionalProperties"]
                if ap is False:
                    errs.append(f"{path}: unexpected property {k!r}")
                elif isinstance(ap, dict):
                    errs += validate(v, ap, root, f"{path}.{k}")
    for sub in sch.get("allOf", []):
        errs += validate(instance, sub, root, path)
    if "anyOf" in sch:
        results = [validate(instance, sub, root, path) for sub in sch["anyOf"]]
        if all(results):
            errs.append(f"{path}: matches no anyOf branch (first branch errors: {results[0][:2]})")
    return errs


def _schema_keywords(node, found=None, in_props=False):
    """Collect keywords used by schema objects (property names under 'properties'/'$defs' are not keywords)."""
    found = set() if found is None else found
    if isinstance(node, dict):
        for k, v in node.items():
            if in_props:
                _schema_keywords(v, found)
                continue
            found.add(k)
            if k in ("properties", "$defs"):
                _schema_keywords(v, found, in_props=True)
            elif k in ("items", "additionalProperties") and isinstance(v, dict):
                _schema_keywords(v, found)
            elif k in ("anyOf", "allOf"):
                for sub in v:
                    _schema_keywords(sub, found)
    return found


def test_validator_supports_every_schema_keyword(schema):
    unknown = _schema_keywords(schema) - SUPPORTED_KEYWORDS - ANNOTATIONS
    assert not unknown, f"schema uses keywords the minimal validator ignores: {sorted(unknown)}"


def test_reference_validates_against_schema(ref, schema):
    errs = validate(ref, schema, schema)
    assert not errs, "\n".join(errs[:20])


@pytest.mark.parametrize("mutation, expect", [
    ("tbd_with_value", "anyOf"),
    ("proposed_without_rationale", "anyOf"),
    ("sourced_without_locator", "anyOf"),
    ("bad_status", "enum"),
    ("extra_top_level_key", "unexpected property"),
    ("wrong_architecture", "enum"),
    ("span_point_without_span_voltages", "anyOf"),
    ("excluded_point_without_reason", "anyOf"),
    ("missing_span_rule", "missing required 'span_rule'"),
])
def test_validator_rejects_bad_instances(ref, schema, mutation, expect):
    bad = copy.deepcopy(ref)
    if mutation == "tbd_with_value":
        bad["geometry_interface"]["fields"]["channel_length_m"]["value"] = 0.05
    elif mutation == "proposed_without_rationale":
        del bad["discharge_voltage_interface"]["proposed_range_V"]["rationale"]
    elif mutation == "sourced_without_locator":
        del bad["discharge_voltage_interface"]["requirements"]["power_max_W"]["locator"]
    elif mutation == "bad_status":
        bad["geometry_interface"]["fields"]["channel_width_m"]["status"] = "GUESS"
    elif mutation == "extra_top_level_key":
        bad["winner"] = "rf_hall"
    elif mutation == "wrong_architecture":
        bad["architectures"] = ["hall_only", "rf_hall", "helicon_hall"]
    elif mutation == "span_point_without_span_voltages":
        op = next(o for o in bad["discharge_voltage_interface"]["literature_operating_points"]
                  if o["span_role"] == "span_defining")
        del op["span_voltages_V"]
    elif mutation == "excluded_point_without_reason":
        op = next(o for o in bad["discharge_voltage_interface"]["literature_operating_points"]
                  if o["span_role"] == "recorded_excluded")
        del op["exclusion_reason"]
    elif mutation == "missing_span_rule":
        del bad["discharge_voltage_interface"]["span_rule"]
    errs = validate(bad, schema, schema)
    assert any(expect in e for e in errs), errs[:5]


# ----------------------------------------------------------------------------------------------- evidence discipline
def _numbers(node, path=(), parents=()):
    if isinstance(node, bool) or node is None or isinstance(node, str):
        return
    if isinstance(node, (int, float)):
        yield path, parents
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _numbers(v, path + (k,), parents + (node,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _numbers(v, path + (i,), parents + (node,))


def _quantities(node, path=()):
    if isinstance(node, dict):
        if "status" in node and "value" in node and "definition" in node:
            yield path, node
        for k, v in node.items():
            yield from _quantities(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _quantities(v, path + (i,))


def _owning_quantity(path, parents):
    """The quantity whose 'value' holds this number (directly or as a list element), else None."""
    for i in range(len(path) - 1, -1, -1):
        p = parents[i]
        if isinstance(p, dict) and path[i] == "value" and "status" in p:
            if all(isinstance(x, int) for x in path[i + 1:]):
                return p
            return None
    return None


def test_every_number_is_sourced_proposed_or_owner_decided(ref):
    bad = []
    n = 0
    for path, parents in _numbers(ref):
        n += 1
        q = _owning_quantity(path, parents)
        where = "/".join(str(p) for p in path)
        if q is None:
            bad.append(f"{where}: number outside a quantity 'value'")
            continue
        if q["status"] not in VALUED_STATUSES:
            bad.append(f"{where}: status {q['status']!r} carries a number")
        if not q.get("source") or q.get("evidence_class") not in EVIDENCE_CLASSES:
            bad.append(f"{where}: missing source or evidence class")
        if q["status"] == "PROPOSED" and not q.get("rationale"):
            bad.append(f"{where}: PROPOSED without rationale")
        if q["status"] in ("SOURCED", "OWNER_DECIDED") and not q.get("locator"):
            bad.append(f"{where}: {q['status']} without locator")
        if not math.isfinite(parents[-1][path[-1]]):
            bad.append(f"{where}: non-finite number")
    assert n > 0
    assert not bad, "\n".join(bad)


def test_tbd_quantities_are_null_and_say_what_they_require(ref):
    tbd = 0
    for path, q in _quantities(ref):
        where = "/".join(str(p) for p in path)
        if q["status"] == "TBD":
            tbd += 1
            assert q["value"] is None, where
            assert q.get("requires", "").startswith("TBD — requires "), where
        else:
            assert q["value"] is not None, f"{where}: {q['status']} with null value"
    assert tbd > 0


def test_source_ids_resolve_and_literature_is_pinned(ref):
    ids = [s["id"] for s in ref["sources"]]
    assert len(ids) == len(set(ids)), "duplicate source ids"
    used = set(re.findall(r'"(SRC-[A-Z0-9-]+)"', json.dumps({k: v for k, v in ref.items() if k != "sources"})))
    assert used <= set(ids), f"unknown source ids: {sorted(used - set(ids))}"
    assert set(ids) <= used, f"sources never cited: {sorted(set(ids) - used)}"
    for s in ref["sources"]:
        if s["kind"] == "open_literature":
            assert re.fullmatch(r"[0-9a-f]{64}", s["sha256"]), s["id"]
            assert s["url_accessed"].startswith("https://"), s["id"]
            assert s["evidence_level"] in {"4", "5", "6"}, s["id"]


def test_repository_sources_and_forbidden_files_exist(ref):
    for s in ref["sources"]:
        if s["kind"] == "repository_file":
            assert os.path.exists(os.path.join(ROOT, s["path"])), f"{s['id']}: {s['path']} missing"
    forbidden = ref["geometry_interface"]["forbidden_value_sources"] + ref["bfield_interface"]["forbidden_value_sources"]
    for entry in forbidden:
        first = entry.split(" ")[0]
        if "/" in first:
            assert os.path.exists(os.path.join(ROOT, first)), f"forbidden-source entry names a missing file: {first}"


def test_other_lane_contracts_are_repo_relative_and_not_required(ref):
    for name, c in ref["related_contracts"].items():
        p = c["path"]
        assert not os.path.isabs(p) and ".claude" not in p and "worktrees" not in p, name
    for s in ref["sources"]:
        if s["kind"] == "other_lane_contract":
            assert not os.path.isabs(s["path"]) and ".claude" not in s["path"], s["id"]


# ----------------------------------------------------------------------------------------------- contracts
def test_architecture_ids_exact(ref):
    assert set(ref["architectures"]) == ARCHITECTURES
    assert set(ref["injection_interface"]["applies_to"]) == ARCHITECTURES
    assert set(ref["bus_power_boundary"]["arm_specific_components"]) == ARCHITECTURES


def test_wall_life_fields_exist_in_hall_map_schema(ref):
    hms = _load(HALL_MAP_SCHEMA_FILE)
    wl = ref["wall_life_interface"]
    assert wl["hall_map_schema_file"] == "hallthruster_bridge/hall_map_schema_v1.json"
    missing = [f for f in wl["hall_map_fields"] if f not in hms["fields"]]
    assert not missing, f"not in hall_map_schema_v1 fields: {missing}"
    missing_meta = [m for m in wl["hall_map_meta"] if m not in hms["meta_required"]]
    assert not missing_meta, f"not in hall_map_schema_v1 meta_required: {missing_meta}"
    for f in ("wall_ion_flux_m2s", "wall_ion_energy_eV", "wall_life_trustworthy"):
        assert f in wl["hall_map_fields"]
    assert "ion_wall_losses" in wl["hall_map_meta"]
    from abep_sim.hall_map import REQUIRED_FIELDS, REQUIRED_META
    assert set(wl["hall_map_fields"]) <= set(REQUIRED_FIELDS)
    assert set(wl["hall_map_meta"]) <= set(REQUIRED_META)
    # wall_life_trustworthy semantics are the schema's, not redefined here
    definition = hms["fields"]["wall_life_trustworthy"]["definition"]
    for cond in wl["wall_life_trustworthy_conditions"]:
        assert cond.lower() in definition.lower(), f"condition {cond!r} not in the schema definition"


def _relation_ids(node, found=None):
    found = set() if found is None else found
    if isinstance(node, dict):
        if "relation" in node and "id" in node:
            found.add(node["id"])
        for v in node.values():
            _relation_ids(v, found)
    elif isinstance(node, list):
        for v in node:
            _relation_ids(v, found)
    return found


def test_evidence_references_resolve(ref):
    rel = _relation_ids(ref)
    for path, q in _quantities(ref):
        for ev in q.get("evidence", []):
            assert ev in rel, f"{'/'.join(map(str, path))}: evidence {ev} is not a relation id"


def test_invariance_rules_cover_geometry_bfield_voltage_and_cathode(ref):
    rules = ref["invariance_rules"]
    ids = [r["id"] for r in rules]
    assert len(ids) == len(set(ids))
    cats = {r["category"] for r in rules}
    assert {"geometry", "bfield", "discharge_voltage", "cathode"} <= cats

    def resolves(ptr):
        node = ref
        for part in ptr[1:].split("/"):
            node = node[int(part)] if isinstance(node, list) else node[part]
        return node

    for r in rules:
        for ptr in r["covers"]:
            resolves(ptr)   # KeyError = dangling pointer

    def covered(ptr, category):
        return any(r["category"] == category and any(ptr == c or ptr.startswith(c + "/") for c in r["covers"])
                   for r in rules)

    required = {
        "geometry": [f"/geometry_interface/fields/{k}" for k in ref["geometry_interface"]["fields"]],
        "bfield": [f"/bfield_interface/fields/{k}" for k in ref["bfield_interface"]["fields"]],
        "discharge_voltage": ["/discharge_voltage_interface/proposed_range_V",
                              "/discharge_voltage_interface/proposed_evaluation_set_V",
                              "/discharge_voltage_interface/supply_definition"],
        "cathode": [f"/cathode_interface/fields/{k}" for k in ref["cathode_interface"]["fields"]],
    }
    gaps = [(cat, p) for cat, ptrs in required.items() for p in ptrs if not covered(p, cat)]
    assert not gaps, f"invariance gaps: {gaps}"


def test_allowed_differences_are_only_injection_preionizer_and_outputs(ref):
    diffs = ref["allowed_differences"]
    assert len(diffs) == 3
    assert "HALL_INLET_Z0" in diffs[0]
    assert "rf_source" in diffs[1] and "ecr_source" in diffs[1] and "ecr_magnet" in diffs[1]


def test_no_p5_or_echt_design_values(ref):
    for section in ("geometry_interface", "bfield_interface"):
        for name, q in ref[section]["fields"].items():
            assert not (set(q.get("source", [])) & P5_ECHT_SOURCE_IDS), f"{section}.{name} cites P5/ECHT as a value source"
            if isinstance(q["value"], str):
                assert "p5_" not in q["value"].lower() and "echt" not in q["value"].lower(), f"{section}.{name}"
    forbidden = " ".join(ref["bfield_interface"]["forbidden_value_sources"])
    for f in os.listdir(os.path.join(ROOT, "hallthruster_bridge", "bfield")):
        if f.endswith(".csv"):
            assert f in forbidden, f"P5 field file {f} is not listed as a forbidden design source"


def test_no_screening_candidate_or_unadmitted_transport(ref):
    tnb = ref["transport_numerics_binding"]
    member = tnb["transport_member_id"]
    from abep_sim.hall_ensemble import member_ids, screening_ids
    if member["value"] is None:
        assert member["status"] == "TBD"
    else:
        assert member["value"] not in screening_ids(), "a screening candidate is not an admitted member"
        assert member["value"] in member_ids(), "transport member is not admitted"
    for path, q in _quantities(ref):
        assert "sgb-screen" not in json.dumps(q.get("value")), f"screening id used as a value at {path}"
    keys = set(tnb["calibration_nuisance_policy"]["keys"])
    ens = _load(os.path.join(ROOT, "hallthruster_bridge", "ensemble", "transport_ensemble_v0.json"))
    assert keys == set(ens["calibration_nuisance"])


def test_solver_pin_matches_pinned_toml(ref):
    from abep_sim.hall_map import pinned_commit
    pin = ref["transport_numerics_binding"]["solver_pin"]
    assert pin["commit"] == pinned_commit()
    text = open(os.path.join(ROOT, "hallthruster_bridge", "PINNED.toml"), encoding="utf-8").read()
    m = re.search(r'^\[hallthruster\].*?^version\s*=\s*"([^"]+)"', text, re.S | re.M)
    assert m and m.group(1) == pin["version"]


def test_bus_components_match_shared_contract(ref):
    bpb = ref["bus_power_boundary"]
    assert bpb["boundary_version"] == "bus_power_boundary_v1"
    names = set(bpb["common_hall_components"]) | set(bpb["other_common_components"])
    for arm in ARCHITECTURES:
        names |= set(bpb["arm_specific_components"][arm])
    assert names == BUS_COMPONENTS
    assert bpb["arm_specific_components"] == {"hall_only": [], "rf_hall": ["rf_source"],
                                              "ecr_hall": ["ecr_source", "ecr_magnet"]}
    assert set(ref["cathode_interface"]["bus_components"]) <= set(bpb["common_hall_components"])


def test_injection_interface_hall_only_is_neutral_only(ref):
    inj = ref["injection_interface"]
    assert inj["plane"]["id"] == "HALL_INLET_Z0"
    fields = inj["inlet_state_fields"]
    for f in ("ion_current_A", "electron_current_A"):
        assert fields[f]["hall_only_rule"] == "exactly zero"
    for f in ("mdot_neutral_kgps", "T_neutral_K", "u_neutral_axial_m_s", "ion_current_A", "u_ion_axial_m_s",
              "T_ion_axial_eV", "electron_current_A", "plasma_potential_rel_anode_V"):
        assert f in fields
    # the pinned solver has no ion inflow at the anode: the reference must say so, not assume it
    assert inj["solver_capability"]["status"] == "GAP"
    assert fields["ion_current_A"]["solver_support"] == "NOT_SUPPORTED"


# ----------------------------------------------------------------------------------------------- voltage interface
def _as_list(v):
    return v if isinstance(v, list) else [v]


def _numeric_bounds(values):
    """(min, max) of a reported voltage list; a string entry like '<100' is an open lower bound (-inf)."""
    lo = min((x for x in values if not isinstance(x, str)), default=None)
    if any(isinstance(x, str) and x.startswith("<") for x in values):
        lo = -math.inf
    return lo, max(x for x in values if not isinstance(x, str))


def test_voltage_set_within_range_and_range_is_the_vr1_span(ref):
    dv = ref["discharge_voltage_interface"]
    lo, hi = dv["proposed_range_V"]["value"]
    vset = dv["proposed_evaluation_set_V"]["value"]
    assert dv["proposed_range_V"]["status"] == "PROPOSED" and dv["proposed_evaluation_set_V"]["status"] == "PROPOSED"
    assert vset == sorted(set(vset)), "evaluation set must be strictly increasing"
    assert vset[0] == lo and vset[-1] == hi, "evaluation set must include both range ends (no extrapolation)"
    rule = dv["span_rule"]
    assert rule["id"] == "VR-1" and "not pre-declared" in rule["provenance_of_rule"].lower()
    span = []
    for op in dv["literature_operating_points"]:
        if op["span_role"] != "span_defining":
            continue
        # VR-1 criteria (a) Hall channel, (b) air species without xenon, (c) measured thrust
        assert op["device_family"] == "hall_channel", op["device"]
        assert op["propellant_family"] == "light" and "xe" not in op["gas"].split("(")[0].lower(), op["device"]
        assert op["thrust_basis"] == "measured", op["device"]
        sv = _as_list(op["span_voltages_V"]["value"])
        rlo, rhi = _numeric_bounds(_as_list(op["discharge_voltage_V"]["value"]))
        assert all(rlo <= v <= rhi for v in sv), f"{op['device']}: span voltages outside its reported range"
        span += sv
    assert span and lo == min(span) and hi == max(span), "range must be the VR-1 span of span-defining points"
    # criterion (c) is applied strictly: a thrust-derived figure (e.g. anodic efficiency) with an unstated thrust basis
    # never counts as a measured thrust (ER-1 holds for an estimated thrust as well)
    assert "needs a measured thrust" not in rule["statement"] and "not satisfy (c)" in rule["statement"]
    for op in dv["literature_operating_points"]:
        if op["span_role"] == "span_defining":
            assert op["span_voltages_V"]["evidence_class"] == "measured", op["device"]
        if op["thrust_basis"] != "measured":
            assert op["span_role"] != "span_defining", op["device"]
    bht = [op for op in dv["literature_operating_points"] if op["device"].startswith("Busek BHT")]
    assert len(bht) == 1 and bht[0]["thrust_basis"] == "not_stated" and bht[0]["span_role"] == "recorded_excluded"
    # the relaxed-(c) alternative is recomputed from the recorded points: span-defining plus 'not_stated' points
    relaxed = list(span)
    for op in bht:
        relaxed.append(_numeric_bounds(_as_list(op["discharge_voltage_V"]["value"]))[1])
    alt = rule["alternative_spans_on_record"]["VR-1-relaxed-c"]
    assert alt["status"] == "PROPOSED" and alt["evidence_class"] == "inferred"
    assert alt["value"] == [min(relaxed), max(relaxed)] == [lo, 350]
    assert (lo, hi) == (180, 305)


def test_every_non_span_point_is_recorded_with_a_reason(ref):
    dv = ref["discharge_voltage_interface"]
    ops = dv["literature_operating_points"]
    for op in ops:
        if op["span_role"] != "span_defining":
            assert op.get("exclusion_reason"), op["device"]
            assert "span_voltages_V" not in op, op["device"]
    names = " ".join(op["device"] for op in ops)
    # the two points an adversarial review found missing from the first draft stay on record
    duk = [op for op in ops if "Dukhopelnikov" in op["device"]]
    mcft = [op for op in ops if "MCFT-2139" in op["device"]]
    assert len(duk) == 1 and len(mcft) == 1, names
    assert duk[0]["span_role"] == "recorded_excluded" and duk[0]["thrust_basis"] == "estimated"
    assert duk[0]["discharge_voltage_V"]["value"] == ["<100", 350]
    assert mcft[0]["span_role"] == "recorded_excluded" and mcft[0]["device_family"] == "cusped_field"
    assert mcft[0]["discharge_voltage_V"]["value"] == [30, 2000]
    # the unfiltered span (criteria a and b only) is recomputed from the recorded points and stated in the rule
    lows, highs = [], []
    for op in ops:
        if op["device_family"] == "hall_channel" and op["propellant_family"] == "light" \
                and "xe" not in op["gas"].split("(")[0].lower():
            lows.append(_numeric_bounds(_as_list(op["discharge_voltage_V"]["value"]))[0])
            highs.append(_numeric_bounds(_as_list(op["discharge_voltage_V"]["value"]))[1])
    unf = dv["span_rule"]["unfiltered_hall_channel_span_V"]["value"]
    assert min(lows) == -math.inf and unf[0] == "<100"
    assert max(highs) == unf[1] == 350


def _load_script():
    spec = importlib.util.spec_from_file_location("hall_reference_voltage_envelope", SCRIPT_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ideal_beam_table_matches_generator(ref):
    mod = _load_script()
    table = ref["discharge_voltage_interface"]["ideal_beam_reference_table"]
    assert table["generated_by"] == "docs/architecture_comparison/hall_reference/voltage_envelope.py"
    assert table["thrust_from"] == "/discharge_voltage_interface/requirements/thrust_mN"
    assert table["power_ceiling_from"] == "/discharge_voltage_interface/requirements/power_max_W"
    assert table["rows"] == mod.expected_table_rows(ref)
    assert set(table["rows"]) == set(table["ions"])
    # physics sanity of the identity: v_b scales as sqrt(V_d / m)
    vset = ref["discharge_voltage_interface"]["proposed_evaluation_set_V"]["value"]
    n2 = table["rows"]["N2+"]["v_b_m_s"]["value"]
    assert n2[-1] / n2[0] == pytest.approx(math.sqrt(vset[-1] / vset[0]), rel=1e-5)
    xe = table["rows"]["Xe+"]["v_b_m_s"]["value"]
    assert n2[0] / xe[0] == pytest.approx(math.sqrt(131.3 / 28.0), rel=1e-5)
    # P_jet = T v_b / 2 at the RFP band ends, and its share of the ceiling
    t_min, t_max = ref["discharge_voltage_interface"]["requirements"]["thrust_mN"]["value"]
    p_max = ref["discharge_voltage_interface"]["requirements"]["power_max_W"]["value"]
    for ion, row in table["rows"].items():
        vb = row["v_b_m_s"]["value"]
        for k, v in enumerate(vb):
            assert row["jet_power_at_thrust_max_kW"]["value"][k] == pytest.approx(t_max * v / 2e6, abs=6e-4)
            assert row["jet_power_at_thrust_min_kW"]["value"][k] == pytest.approx(t_min * v / 2e6, abs=6e-4)
            assert row["jet_power_at_thrust_max_fraction_of_power_max"]["value"][k] == pytest.approx(
                t_max * v / 2e6 / (p_max / 1e3), abs=6e-4)


def test_generator_refuses_missing_inputs(ref):
    mod = _load_script()
    band, pmax = [12, 25], 1500
    with pytest.raises(ValueError):
        mod.compute_rows([], ["N2+"], band, pmax)
    with pytest.raises(ValueError):
        mod.compute_rows([200], [], band, pmax)
    with pytest.raises(ValueError):
        mod.compute_rows([200], ["He+"], band, pmax)
    with pytest.raises(ValueError):
        mod.compute_rows([-5], ["N2+"], band, pmax)
    for bad_band in (None, [25], [25, 12], [0, 25], [12, None]):
        with pytest.raises(ValueError):
            mod.compute_rows([200], ["N2+"], bad_band, pmax)
    for bad_p in (None, 0, -1500):
        with pytest.raises(ValueError):
            mod.compute_rows([200], ["N2+"], band, bad_p)
    # a TBD requirement (null value) is refused, never defaulted
    bad = copy.deepcopy(ref)
    bad["discharge_voltage_interface"]["requirements"]["power_max_W"]["value"] = None
    with pytest.raises(ValueError):
        mod.expected_table_rows(bad)


# ----------------------------------------------------------------------------------------------- measured (T, P_d) pairs
def test_measured_pairs_match_generator(ref):
    mod = _load_script()
    chk = ref["discharge_voltage_interface"]["measured_discharge_power_check"]
    assert chk["generated_by"] == "docs/architecture_comparison/hall_reference/voltage_envelope.py"
    assert chk["power_ceiling_from"] == "/discharge_voltage_interface/requirements/power_max_W"
    expected = mod.expected_pair_derived(ref)
    ids = [pt["id"] for pt in chk["points"]]
    assert len(ids) == len(set(ids)) and set(ids) == set(expected)
    p_max = ref["discharge_voltage_interface"]["requirements"]["power_max_W"]["value"]
    for pt in chk["points"]:
        assert pt["derived"] == expected[pt["id"]], pt["id"]
        # the inputs are published measurements, the derived numbers model-derived arithmetic on them
        for k in ("discharge_voltage_V", "discharge_current_A", "thrust_mN"):
            assert pt[k]["status"] == "SOURCED" and pt[k]["evidence_class"] == "measured", (pt["id"], k)
        for q in pt["derived"].values():
            assert q["evidence_class"] == "model-derived" and "SRC-VENV-SCRIPT" in q["source"]
        v, i = pt["discharge_voltage_V"]["value"], pt["discharge_current_A"]["value"]
        t_lo, t_hi = pt["thrust_mN"]["value"]
        d = pt["derived"]
        assert d["discharge_power_W"]["value"] == pytest.approx(v * i, abs=0.06)
        assert d["discharge_power_fraction_of_power_max"]["value"] == pytest.approx(v * i / p_max, abs=6e-4)
        assert d["thrust_per_discharge_power_mN_per_kW"]["value"] == pytest.approx(
            [t_lo / (v * i) * 1e3, t_hi / (v * i) * 1e3], abs=6e-3)
        # eta* = P_jet,ideal / P_d with the reference ion's ideal beam velocity
        vb = mod.beam_velocity_m_s(v, mod.ion_mass_kg(chk["reference_ion"]))
        assert d["eta_star_reference_ion"]["value"] == pytest.approx(
            [t_lo * vb / 2e3 / (v * i), t_hi * vb / 2e3 / (v * i)], abs=6e-4)
    # every measured pair is a published air-species point inside or just below the RFP thrust band
    t_max = ref["discharge_voltage_interface"]["requirements"]["thrust_mN"]["value"][1]
    for pt in chk["points"]:
        assert pt["thrust_mN"]["value"][1] <= t_max and "xe" not in pt["gas"].split("(")[0].lower(), pt["id"]


def test_eta_star_is_not_the_anodic_efficiency(ref):
    """The ideal-beam jet power is never divided by an anodic efficiency (P_d != P_jet,ideal / eta_a)."""
    text = json.dumps(ref) + open(DOC_FILE, encoding="utf-8").read() + open(SCRIPT_FILE, encoding="utf-8").read()
    for bad in ("P_jet / efficiency", "P_d = P_jet / eta", "P_jet/efficiency"):
        assert bad not in text, bad
    defs = ref["discharge_voltage_interface"]["measured_discharge_power_check"]["efficiency_definitions"]
    assert "eta_a / (gamma eta_m sqrt(eta_v))" in defs and "NEVER" in defs
    rows = ref["discharge_voltage_interface"]["ideal_beam_reference_table"]["rows"]
    for row in rows.values():
        for k in ("jet_power_at_thrust_min_kW", "jet_power_at_thrust_max_kW"):
            assert "P_d is NOT P_jet / eta_a" in row[k]["uncertainty"]
    # ECHT Run 2: eta* (N2+) exceeds its reconstructed anodic efficiency (0.23, echt_table_checks_v1.json) by > 3x,
    # so applying eta_a to the ideal-beam jet power would overstate P_d several-fold
    checks = _load(os.path.join(ROOT, "hallthruster_bridge", "identification", "echt_n2", "echt_table_checks_v1.json"))
    eta_a = {r["run"]: r["eta_anode_T2_over_2mPa"] for r in checks["runs"]}
    pts = {pt["id"]: pt for pt in ref["discharge_voltage_interface"]["measured_discharge_power_check"]["points"]}
    run2 = pts["ECHT-Run2"]
    assert run2["derived"]["eta_star_reference_ion"]["value"][1] > 3 * eta_a["Run 2"]
    # the ECHT inputs are the audit's transcription
    by_run = {r["run"]: r for r in checks["runs"]}
    for pid, pt in pts.items():
        if pid.startswith("ECHT-"):
            r = by_run[pid.replace("ECHT-Run", "Run ")]
            assert pt["discharge_voltage_V"]["value"] == r["Vd"] and pt["discharge_current_A"]["value"] == r["Id"]
            assert pt["thrust_mN"]["value"] == [r["T_avg_mN"], r["T_mN"]]


def test_document_quotes_measured_pairs(ref):
    doc = open(DOC_FILE, encoding="utf-8").read()
    rat = ref["discharge_voltage_interface"]["proposed_range_V"]["rationale"]
    pts = ref["discharge_voltage_interface"]["measured_discharge_power_check"]["points"]
    for pt in pts:
        d = pt["derived"]
        t = pt["thrust_mN"]["value"]
        tp = d["thrust_per_discharge_power_mN_per_kW"]["value"]
        es = d["eta_star_reference_ion"]["value"]
        line = (f"| {pt['id']} | {pt['discharge_voltage_V']['value']} | {pt['discharge_current_A']['value']} | "
                f"{t[0]}–{t[1]} | {d['discharge_power_W']['value']} | {tp[0]}–{tp[1]} | "
                f"{round(d['discharge_power_fraction_of_power_max']['value'] * 100, 1)} % | {es[0]}–{es[1]} |")
        assert line in doc, f"document row for {pt['id']} differs from the JSON"
    t_lo = min(pt["thrust_mN"]["value"][0] for pt in pts)
    t_hi = max(pt["thrust_mN"]["value"][1] for pt in pts)
    p_lo = min(pt["derived"]["discharge_power_W"]["value"] for pt in pts) / 1e3
    p_hi = max(pt["derived"]["discharge_power_W"]["value"] for pt in pts) / 1e3
    f_lo = min(pt["derived"]["discharge_power_fraction_of_power_max"]["value"] for pt in pts)
    f_hi = max(pt["derived"]["discharge_power_fraction_of_power_max"]["value"] for pt in pts)
    tp_lo = min(pt["derived"]["thrust_per_discharge_power_mN_per_kW"]["value"][0] for pt in pts)
    tp_hi = max(pt["derived"]["thrust_per_discharge_power_mN_per_kW"]["value"][1] for pt in pts)
    assert f"{t_lo}–{t_hi} mN" in doc and f"{p_lo}–{p_hi} kW" in doc, (t_lo, t_hi, p_lo, p_hi)
    assert f"{round(f_lo * 100, 1)}–{round(f_hi * 100, 1)} % of the 1.5 kW ceiling for the discharge alone" in doc
    assert f"{tp_lo}–{tp_hi} mN/kW" in doc
    assert f"{t_lo}-{t_hi} mN" in rat and f"{p_lo}-{p_hi} kW" in rat and f"{tp_lo}-{tp_hi} mN/kW" in rat
    assert f"{round(f_lo * 100, 1)}-{round(f_hi * 100, 1)} % of the 1.5 kW ceiling" in rat


def test_efficiency_independent_voltage_floor_is_singly_charged_only(ref):
    er5 = {e["id"]: e for e in ref["discharge_voltage_interface"]["envelope_relations"]}["ER-5"]
    assert "singly charged" in er5["relation"] and "multiply charged" in er5["relation"]
    assert "singly charged" in er5["applicability"]
    doc = open(DOC_FILE, encoding="utf-8").read()
    assert "holds only for a singly charged beam" in doc


def test_unwired_solver_fields_are_labelled(ref):
    f = ref["geometry_interface"]["fields"]
    for name in ("wall_material", "magnetically_shielded"):
        assert "SUPPORTED_NOT_WIRED" in f[name]["maps_to"], name
    assert "Solver-supported, not wired in the bridge" in open(DOC_FILE, encoding="utf-8").read()


def test_textbook_summaries_are_not_classed_measured(ref):
    ev = {r["id"]: r for r in ref["geometry_interface"]["sizing_relations"]}["EV-G8"]
    for q in ev["stated_values"].values():
        assert q["evidence_class"] != "measured"
    for op in ref["discharge_voltage_interface"]["literature_operating_points"]:
        if op["span_role"] == "context_only" and op["propellant_family"] == "xenon":
            assert op["discharge_voltage_V"]["evidence_class"] != "measured", op["device"]


# ----------------------------------------------------------------------------------------------- document
def test_document_matches_reference(ref):
    doc = open(DOC_FILE, encoding="utf-8").read()
    for r in ref["invariance_rules"]:
        assert r["id"] in doc, f"{r['id']} not described in HALL_ACCELERATOR_REFERENCE.md"
    for token in ("hall_reference_v1.json", "schemas/architecture_comparison/hall_reference_v1.schema.json",
                  "Milestone A", "Milestone B", "Milestone C", "HALL_INLET_Z0", "PROPOSED", "TBD", "GAP"):
        assert token in doc, token
    for arm in ARCHITECTURES:
        assert arm in doc
    for s in ref["sources"]:
        if s["kind"] == "open_literature":
            assert s["sha256"] in doc and s["url_accessed"] in doc, s["id"]
    # the ideal-beam numbers quoted in the document are exactly the JSON's (which the generator reproduces)
    rows = ref["discharge_voltage_interface"]["ideal_beam_reference_table"]["rows"]
    vset = ref["discharge_voltage_interface"]["proposed_evaluation_set_V"]["value"]
    assert "| ion | " + " | ".join(f"{v} V" for v in vset) + " |" in doc
    for ion, r in rows.items():
        line = f"| {ion} | " + " | ".join(str(x) for x in r["thrust_per_jet_power_mN_per_kW"]["value"]) + " |"
        assert line in doc, f"document T/P_jet row for {ion} differs from the JSON"
        pj = r["jet_power_at_thrust_max_kW"]["value"]
        fr = r["jet_power_at_thrust_max_fraction_of_power_max"]["value"]
        line = f"| {ion} | " + " | ".join(f"{a} ({round(b * 100, 1)} %)" for a, b in zip(pj, fr)) + " |"
        assert line in doc, f"document P_jet row for {ion} differs from the JSON"
    # the envelope-tie sentence quotes the extreme air-species cells of the JSON table
    cells = [(rows[i]["jet_power_at_thrust_max_kW"]["value"][k],
              rows[i]["jet_power_at_thrust_max_fraction_of_power_max"]["value"][k])
             for i in ("N2+", "N+", "O2+", "O+") for k in range(len(vset))]
    (p_lo, f_lo), (p_hi, f_hi) = min(cells), max(cells)
    assert f"needs {p_lo} kW" in doc and f"to {p_hi} kW" in doc
    assert f"{round(f_lo * 100, 1)}–{round(f_hi * 100, 1)} % of the 1.5 kW ceiling" in doc
    rat = ref["discharge_voltage_interface"]["proposed_range_V"]["rationale"]
    assert f"{p_lo} kW" in rat and f"{p_hi} kW" in rat and f"{round(f_lo * 100, 1)}-{round(f_hi * 100, 1)} %" in rat
    # every literature point (including the excluded ones) is in the document table
    for op in ref["discharge_voltage_interface"]["literature_operating_points"]:
        key = "Dukhopelnikov" if "Dukhopelnikov" in op["device"] else op["device"].split(" (")[0].split(" ")[0]
        assert key.lower() in doc.lower(), key
    assert "VR-1" in doc and "not pre-declared" in doc


def test_provisional_contract_mappings_are_labelled(ref):
    fields = ref["injection_interface"]["inlet_state_fields"]
    te = fields["T_e_inlet_eV"]["interstage_field"]
    assert te.startswith("SOURCE-EXIT value, not an inlet-plane value"), te
    for c in ("interstage", "upstream_icd", "hallmap_spec", "cathode_integration"):
        assert "not merged" in ref["related_contracts"][c]["status_at_authoring"] \
            or "not reproducible" in ref["related_contracts"][c]["status_at_authoring"].lower(), c
    note = ref["transport_numerics_binding"]["solver_settings"]["cathode_coupling_voltage_V"]["notes"]
    assert "PLACEHOLDER" in note and "NOT a design" in note
    inv = {r["id"]: r for r in ref["invariance_rules"]}["INV-C2"]["rule"]
    assert "placeholder" in inv and "not a design value" in inv
