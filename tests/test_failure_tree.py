"""Tests for the architecture-specific failure trees (lane 26, FTREE).

docs/architecture_comparison/failure_tree/failure_trees_v1.json against
schemas/architecture_comparison/failure_tree_v1.schema.json, plus the content rules the schema cannot express:
evidence-status rule, resolving actions, gate links, failure-class coverage per architecture, evidence discipline,
no winner, the ranking rule (recomputed independently here) and reproduction of the generated parts.

Needs only the standard library, scipy (already a dependency) and abep_sim.constants. It does not need any other lane's
deliverable (arch_boundary, arch_compare, hard-gate matrix, ...), and it runs no Hall model.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FT_DIR = ROOT / "docs" / "architecture_comparison" / "failure_tree"
JSON_PATH = FT_DIR / "failure_trees_v1.json"
MD_PATH = FT_DIR / "FAILURE_TREES.md"
GEN_PATH = FT_DIR / "derive_failure_tree.py"
SCHEMA_PATH = ROOT / "schemas" / "architecture_comparison" / "failure_tree_v1.schema.json"

ARCHS = ("hall_only", "rf_hall", "ecr_hall")
GATES = ("thrust", "bus_power", "mass", "firing_life", "mission_life", "restart_sustainment", "air_xe")
MATRIX_IDS = {"thrust": "G1_thrust", "bus_power": "G2_bus_power", "mass": "G3_mass", "firing_life": "G4_firing_life",
              "mission_life": "G5_mission", "restart_sustainment": "G6_ignition_sustainment", "air_xe": "G7_air_xenon"}
GENERIC_CLASSES = {"ignition", "sustainment_extinction", "utilization", "cathode_limit", "thermal_limit",
                   "erosion_wall_life", "power_limit", "mass_limit", "control_startup"}
COST = {"literature": 0, "analysis": 1, "measurement": 2}


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ minimal JSON Schema validator
ALLOWED_KEYWORDS = {"$schema", "$id", "$defs", "$ref", "title", "description", "type", "required", "properties",
                    "additionalProperties", "items", "enum", "const", "pattern", "minItems", "uniqueItems", "minLength",
                    "minimum", "maximum"}
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool}


def _type_ok(x, t):
    if t == "integer":
        return isinstance(x, int) and not isinstance(x, bool)
    if t == "number":
        return isinstance(x, (int, float)) and not isinstance(x, bool)
    return isinstance(x, _TYPES[t])


def _validate(x, s, root, path, errs):
    if "$ref" in s:
        ref = s["$ref"]
        assert ref.startswith("#/$defs/"), ref
        _validate(x, root["$defs"][ref[len("#/$defs/"):]], root, path, errs)
        return
    if "type" in s and not _type_ok(x, s["type"]):
        errs.append(f"{path}: expected {s['type']}, got {type(x).__name__}")
        return
    if "const" in s and x != s["const"]:
        errs.append(f"{path}: {x!r} != const {s['const']!r}")
    if "enum" in s and x not in s["enum"]:
        errs.append(f"{path}: {x!r} not in {s['enum']}")
    if isinstance(x, str):
        if "minLength" in s and len(x) < s["minLength"]:
            errs.append(f"{path}: shorter than {s['minLength']}")
        if "pattern" in s and not re.search(s["pattern"], x):
            errs.append(f"{path}: {x!r} does not match {s['pattern']}")
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        if "minimum" in s and x < s["minimum"]:
            errs.append(f"{path}: {x} < {s['minimum']}")
        if "maximum" in s and x > s["maximum"]:
            errs.append(f"{path}: {x} > {s['maximum']}")
    if isinstance(x, list):
        if "minItems" in s and len(x) < s["minItems"]:
            errs.append(f"{path}: fewer than {s['minItems']} items")
        if s.get("uniqueItems") and len({json.dumps(i, sort_keys=True) for i in x}) != len(x):
            errs.append(f"{path}: items not unique")
        if "items" in s:
            for i, it in enumerate(x):
                _validate(it, s["items"], root, f"{path}[{i}]", errs)
    if isinstance(x, dict):
        for k in s.get("required", []):
            if k not in x:
                errs.append(f"{path}: missing required {k!r}")
        props = s.get("properties", {})
        for k, v in x.items():
            if k in props:
                _validate(v, props[k], root, f"{path}.{k}", errs)
            elif s.get("additionalProperties") is False:
                errs.append(f"{path}: unexpected property {k!r}")


def _keywords(s, out):
    if isinstance(s, dict):
        for k, v in s.items():
            out.add(k)
            if k in ("properties", "$defs"):
                for sub in v.values():
                    _keywords(sub, out)
            elif k in ("items", "additionalProperties") and isinstance(v, dict):
                _keywords(v, out)
    return out


def test_schema_uses_only_supported_keywords(schema):
    assert _keywords(schema, set()) <= ALLOWED_KEYWORDS


def test_validator_rejects_bad_documents(doc, schema):
    bad = json.loads(json.dumps(doc))
    bad["nodes"][0]["evidence_status"] = "probable"
    bad["nodes"][1]["decision_quantity"]["gates"] = ["thrust_ok"]
    bad["nodes"][2]["surprise"] = 1
    errs = []
    _validate(bad, schema, schema, "$", errs)
    assert len(errs) >= 3, errs


def test_document_validates_against_schema(doc, schema):
    errs = []
    _validate(doc, schema, schema, "$", errs)
    assert not errs, "\n".join(errs[:30])


# ------------------------------------------------------------------ nodes: status and resolving action
def _status_from_evidence(node):
    dirs = {e["direction"] for e in node["evidence"]}
    sup, con = "supports" in dirs, "contradicts" in dirs
    if sup and not con:
        return "supported"
    if con and not sup:
        return "contradicted"
    return "unknown"


def test_node_ids_unique(doc):
    ids = [n["id"] for n in doc["nodes"]]
    assert len(ids) == len(set(ids))


def test_every_node_has_evidence_status_following_the_rule(doc):
    for n in doc["nodes"]:
        assert n["evidence_status"] in ("supported", "contradicted", "unknown"), n["id"]
        assert n["evidence_status"] == _status_from_evidence(n), n["id"]
        dirs = {e["direction"] for e in n["evidence"]}
        if not dirs & {"supports", "contradicts"}:
            # unknown for lack of decisive evidence (none, or context only): the gap must be stated
            assert n.get("evidence_gap"), f"{n['id']}: nothing decisive, needs an evidence_gap"


def test_every_node_has_a_resolving_action(doc):
    acts = {a["id"]: a for a in doc["actions"]}
    for n in doc["nodes"]:
        assert n["actions"], n["id"]
        for na in n["actions"]:
            assert na["action"] in acts, (n["id"], na["action"])
        assert len({na["action"] for na in n["actions"]}) == len(n["actions"]), n["id"]
        decides = [na["action"] for na in n["actions"] if na["effect"] == "decides"]
        contributes = [na["action"] for na in n["actions"] if na["effect"] == "contributes"]
        # resolvable: at least one action that decides it, or a jointly sufficient set of contributors
        assert decides or len(contributes) >= 2, n["id"]
        # some resolving route is not blocked
        unblocked = [a for a in decides + contributes if not acts[a]["blocked_by"]]
        assert unblocked, n["id"]
        assert n["milestone_A_condition"].strip(), n["id"]


def test_cheapest_resolution_rule(doc):
    """Either one 'decides' action, or a set of >= 2 'contributes' actions; never blocked; cost class not above the
    cheapest 'decides' action of the node."""
    acts = {a["id"]: a for a in doc["actions"]}
    for n in doc["nodes"]:
        eff = {na["action"]: na["effect"] for na in n["actions"]}
        cr = n["cheapest_resolution"]
        for a in cr:
            assert a in eff, (n["id"], a)
            assert not acts[a]["blocked_by"], (n["id"], a)
        if len(cr) == 1:
            assert eff[cr[0]] == "decides", n["id"]
        else:
            assert all(eff[a] == "contributes" for a in cr), n["id"]
        dec_costs = [COST[acts[a]["kind"]] for a, e in eff.items() if e == "decides" and not acts[a]["blocked_by"]]
        if dec_costs:
            assert max(COST[acts[a]["kind"]] for a in cr) <= min(dec_costs), n["id"]


# ------------------------------------------------------------------ gates
def test_hard_gates_are_the_rfp_set_with_rfp_numbers(doc):
    from abep_sim.constants import RFP
    gates = {g["id"]: g for g in doc["hard_gates"]}
    assert tuple(g["id"] for g in doc["hard_gates"]) == GATES
    for g in doc["hard_gates"]:
        for v in g["threshold"]["values"]:
            name = v["rfp_constant"]
            assert name.startswith("RFP."), name
            assert v["value"] == getattr(RFP, name[4:]), (g["id"], name)
        if g["threshold_status"] != "RFP":
            assert g.get("tbd", "").startswith("TBD"), g["id"]
    assert gates["thrust"]["threshold"]["values"][0]["value"] == RFP.thrust_min_mN


def test_gate_links_reference_valid_gate_names(doc):
    valid = {g["id"] for g in doc["hard_gates"]}
    assert valid == set(GATES)
    for n in doc["nodes"]:
        assert n["decision_quantity"]["gates"], n["id"]
        assert set(n["decision_quantity"]["gates"]) <= valid, n["id"]
    for e in doc["eliminations"]:
        assert e["gate"] in valid


def test_gate_links_to_hard_gate_matrix_ids(doc):
    link = doc["hard_gate_matrix_link"]
    for g in doc["hard_gates"]:
        assert g["matrix_gate_id"] == MATRIX_IDS[g["id"]]
    assert set(link["binding_gates"]) == set(MATRIX_IDS.values())
    for n in doc["nodes"]:
        assert set(n.get("proposed_gate_links", [])) <= set(link["proposed_gates"]), n["id"]


def test_every_gate_is_reached_by_every_architecture(doc):
    for arch in ARCHS:
        reached = {g for n in doc["nodes"] if arch in n["architectures"] for g in n["decision_quantity"]["gates"]}
        assert reached == set(GATES), (arch, set(GATES) - reached)


def test_threshold_status_discipline(doc):
    """RFP numbers only on RFP-status thresholds; everything else is PROPOSED, TBD or a physics bound."""
    for n in doc["nodes"]:
        dq = n["decision_quantity"]
        if dq["threshold_status"] == "TBD":
            assert "TBD" in dq["threshold"], n["id"]
        if dq["threshold_status"] == "PROPOSED":
            assert "PROPOSED" in dq["threshold"], n["id"]


# ------------------------------------------------------------------ coverage
def test_every_architecture_covers_every_generic_failure_class(doc):
    classes = {c["id"]: c for c in doc["failure_classes"]}
    assert {c["name"] for c in doc["failure_classes"] if c["generic"]} == GENERIC_CLASSES
    for c in doc["failure_classes"]:
        if c["generic"]:
            assert set(c["applies_to"]) == set(ARCHS), c["id"]
    for arch in ARCHS:
        present = {classes[n["failure_class"]]["name"] for n in doc["nodes"] if arch in n["architectures"]}
        assert GENERIC_CLASSES <= present, (arch, GENERIC_CLASSES - present)
        for c in doc["failure_classes"]:
            if arch in c["applies_to"]:
                assert c["name"] in present, (arch, c["id"])


def test_architecture_specific_classes_and_modes(doc):
    classes = {c["id"]: c for c in doc["failure_classes"]}
    by_name = {c["name"]: c for c in doc["failure_classes"]}
    assert set(by_name["interstage_loss"]["applies_to"]) == {"rf_hall", "ecr_hall"}
    assert set(by_name["rf_source_specific"]["applies_to"]) == {"rf_hall"}
    assert set(by_name["ecr_source_specific"]["applies_to"]) == {"ecr_hall"}
    for n in doc["nodes"]:
        assert n["failure_class"] in classes, n["id"]
        assert set(n["architectures"]) <= set(classes[n["failure_class"]]["applies_to"]), n["id"]
    text = {arch: " ".join(n["title"] + " " + n["mechanism"] for n in doc["nodes"] if arch in n["architectures"]).lower()
            for arch in ARCHS}
    assert "e-h" in text["rf_hall"]                                    # RF E-H mode transition
    assert "cutoff" in text["ecr_hall"] and "overdense" in text["ecr_hall"]
    assert "hall magnetic circuit" in text["ecr_hall"]                 # ECR magnets vs Hall circuit
    for arch in ("rf_hall", "ecr_hall"):
        assert any(classes[n["failure_class"]]["name"] == "interstage_loss" and n["architectures"] == [arch]
                   for n in doc["nodes"]), arch
    assert not any(classes[n["failure_class"]]["name"] == "interstage_loss" and "hall_only" in n["architectures"]
                   for n in doc["nodes"])


def test_common_elements_carry_all_three_architectures(doc):
    """Cathode, mass-total, bus loads and the Xe->air transition are common downstream elements."""
    classes = {c["id"]: c["name"] for c in doc["failure_classes"]}
    for n in doc["nodes"]:
        if "cathode" in n["rfp_blocks"] and classes[n["failure_class"]] == "cathode_limit":
            assert set(n["architectures"]) == set(ARCHS), n["id"]


# ------------------------------------------------------------------ evidence discipline
def test_evidence_items_cite_known_readable_sources(doc):
    src = {s["id"]: s for s in doc["sources"]}
    assert len(src) == len(doc["sources"])
    for n in doc["nodes"]:
        for e in n["evidence"]:
            assert e["source"] in src, (n["id"], e["source"])
            assert src[e["source"]]["access"] != "identified_not_read", (n["id"], e["source"])
            assert e["locator"].strip() and e["applicability"].strip(), n["id"]
    for s in doc["sources"]:
        if s["access"] == "full_text_open":
            assert "sha256" in s, s["id"]
        assert s.get("doi") or s.get("arxiv") or s.get("report_id") or s["access"] == "identified_not_read", s["id"]


def test_action_targets_and_lanes_exist(doc):
    src = {s["id"] for s in doc["sources"]}
    lanes = {l["id"] for l in doc["lanes"]}
    for a in doc["actions"]:
        assert a["lane"] in lanes, a["id"]
        assert a["id"][0] == {"literature": "L", "analysis": "A", "measurement": "M"}[a["kind"]], a["id"]
        for t in a.get("targets", []):
            assert t in src, (a["id"], t)
    for d in (n["decision_quantity"].get("derived_values", []) for n in doc["nodes"]):
        known = {v["id"] for v in doc["derived_values"]["values"]}
        assert set(d) <= known


def test_no_hall_closure_or_screening_candidate_as_evidence(doc):
    blob = json.dumps(doc["nodes"]) + json.dumps(doc["sources"])
    assert "sgb-screen" not in blob
    acts = {a["id"]: a for a in doc["actions"]}
    blocked = {a for a, v in acts.items() if v["blocked_by"]}
    assert blocked == {"A-HALLMAP"}
    for n in doc["nodes"]:
        for na in n["actions"]:
            if na["action"] in blocked:
                assert na["effect"] == "informs", n["id"]
        if n.get("upstream_hall_independent"):
            # the upstream half is resolved by the Hall-independent feed analysis; no Hall map may feed it
            ids = {na["action"] for na in n["actions"]}
            assert "A-HALLMAP" not in ids, n["id"]
            assert "A-FLOWENV" in ids, n["id"]
            assert "gas_supply_upstream" in n["rfp_blocks"], n["id"]
    assert "hall" not in acts["A-FLOWENV"]["description"].lower().replace("uses no hall input", "")


def test_no_winner_and_no_elimination(doc):
    assert doc["eliminations"] == []
    assert doc["elimination_rule"]["status"] == "PROPOSED"
    assert all(n["decision_state"] == "open" for n in doc["nodes"])
    assert "no winner" in doc["no_winner_statement"].lower()
    assert doc["milestones"]["supports"] == ["A"]


def test_derived_values_reproduce_source_statements(doc):
    for v in doc["derived_values"]["values"]:
        cc = v.get("cross_check")
        if cc:
            assert abs(cc["rel_diff"]) < 0.05, v["id"]


# ------------------------------------------------------------------ ranking and generator
def _rank_independent(doc, arch):
    gates_of = {n["id"]: set(n["decision_quantity"]["gates"]) for n in doc["nodes"]}
    nodes = [n for n in doc["nodes"] if arch in n["architectures"] and n["decision_state"] == "open"]
    rows = []
    for a in doc["actions"]:
        if a["blocked_by"]:
            continue
        eff = {"decides": set(), "contributes": set(), "informs": set()}
        for n in nodes:
            for na in n["actions"]:
                if na["action"] == a["id"]:
                    eff[na["effect"]].add(n["id"])
        if not any(eff.values()):
            continue
        g = set().union(*[gates_of[x] for x in eff["decides"]]) if eff["decides"] else set()
        rows.append(((-len(eff["decides"]), -len(g), -len(eff["contributes"]), -len(eff["informs"]),
                      COST[a["kind"]], a["id"]), a["id"]))
    return [r[1] for r in sorted(rows)]


def test_ranking_follows_the_stated_rule(doc):
    rule = doc["ranking_rule"]
    assert rule["id"] == doc["ranked_next_evidence"]["rule_id"] == "decisiveness_lexicographic_v1"
    assert rule["cost_rank"] == COST
    for arch in ARCHS:
        r = doc["ranked_next_evidence"]["per_architecture"][arch]
        assert [x["action"] for x in r["ranked"]] == _rank_independent(doc, arch), arch
        assert [x["rank"] for x in r["ranked"]] == list(range(1, len(r["ranked"]) + 1))
        assert {b["action"] for b in r["blocked"]} <= {"A-HALLMAP"}
        assert r["n_nodes"] == sum(1 for n in doc["nodes"] if arch in n["architectures"])
        assert r["ranked"], arch


def _load_generator():
    spec = importlib.util.spec_from_file_location("derive_failure_tree", GEN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generated_json_and_markdown_are_up_to_date(doc):
    gen = _load_generator()
    new_json, sections = gen.build(doc)
    assert new_json == JSON_PATH.read_text(encoding="utf-8"), "run derive_failure_tree.py"
    md = MD_PATH.read_text(encoding="utf-8")
    assert gen.splice(md, sections) == md, "run derive_failure_tree.py"


def test_generator_imports_no_other_lane_module():
    src = GEN_PATH.read_text(encoding="utf-8")
    for mod in ("arch_boundary", "arch_compare", "thermal_life", "breakeven", "interstage", "cathode_integration",
                "hall_map", "hall_ensemble", "archengine"):
        assert not re.search(rf"^\s*(from|import)\s+\S*{mod}", src, re.M), mod
