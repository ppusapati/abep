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
        extra = s.get("additionalProperties", True)
        for k, v in x.items():
            if k in props:
                _validate(v, props[k], root, f"{path}.{k}", errs)
            elif extra is False:
                errs.append(f"{path}: unexpected property {k!r}")
            elif isinstance(extra, dict):
                _validate(v, extra, root, f"{path}.{k}", errs)


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


def test_validator_applies_schema_valued_additional_properties():
    s = {"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": {"type": "integer"}}
    errs = []
    _validate({"a": "x", "b": 1}, s, s, "$", errs)
    assert not errs
    _validate({"a": "x", "b": "not an integer"}, s, s, "$", errs)
    assert errs and "$.b" in errs[0]


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


def test_requires_actions_forbid_a_lone_decides(doc):
    """'decides' means sufficient alone given only owner-fixed and design-fixed inputs. An action named in
    decision_quantity.requires_actions (another action's output the threshold comparison needs) therefore forbids any
    other action from deciding the node; each required action contributes and is in cheapest_resolution."""
    assert set(doc["action_effects"]) == {"decides", "contributes", "informs", "rule"}
    acts = {a["id"] for a in doc["actions"]}
    for n in doc["nodes"]:
        dq = n["decision_quantity"]
        req = set(dq["requires_actions"])
        assert req <= acts, n["id"]
        eff = {na["action"]: na["effect"] for na in n["actions"]}
        # every action id named in the free-text 'requires' is listed in requires_actions
        assert set(re.findall(r"\b[LAM]-[A-Z0-9]+\b", dq.get("requires", ""))) <= req, n["id"]
        for a in req:
            assert eff.get(a) in ("decides", "contributes"), (n["id"], a)
            assert a in n["cheapest_resolution"], (n["id"], a)
        for a, e in eff.items():
            if e == "decides":
                assert req <= {a}, f"{n['id']}: {a} cannot decide while {sorted(req - {a})} is required"


def test_contributes_forms_a_jointly_sufficient_set(doc):
    """A 'contributes' action is never sufficient alone, so a node's contributing actions are either absent or at
    least two (a lone contributor beside a decider would really only inform)."""
    for n in doc["nodes"]:
        c = [na["action"] for na in n["actions"] if na["effect"] == "contributes"]
        assert len(c) != 1, (n["id"], c)


def test_regression_requires_relabelled_nodes(doc):
    """Nodes whose threshold needs another action's output (review round 1) have no lone decider."""
    nodes = {n["id"]: n for n in doc["nodes"]}
    for nid in ("N-PWR-01", "N-PWR-02", "N-PWR-03", "N-UTL-01", "N-UTL-02", "N-UTL-03", "N-ISL-RF", "N-ISL-ECR",
                "N-ECR-01", "N-SUS-02", "N-CAT-02", "N-CTL-02"):
        assert not [na for na in nodes[nid]["actions"] if na["effect"] == "decides"], nid


_UNSTATED_GAS = re.compile(r"(gas|composition)[^.;]{0,60}(not stated|does not state)|does not state the (gas|composition)", re.I)


def test_unstated_gas_is_not_decisive_for_air_nodes(doc):
    """An item whose source does not state the gas/composition for the cited result (gas_not_stated) cannot support or
    contradict an air_specific node: it is 'context' until the gas is known. The rule is keyed on the explicit
    air_specific and gas_not_stated flags, not on titles, and the flags cannot be dropped silently:
    - an applicability text that says the gas is not stated must carry gas_not_stated;
    - once a source has an unstated-gas item anywhere, each of its decisive items on an air_specific node must name the
      gas the source states for that result (gas_stated)."""
    unstated_sources = {e["source"] for n in doc["nodes"] for e in n["evidence"] if e.get("gas_not_stated")}
    for n in doc["nodes"]:
        assert isinstance(n["air_specific"], bool), n["id"]
        for e in n["evidence"]:
            if _UNSTATED_GAS.search(e["applicability"]):
                assert e.get("gas_not_stated") is True, (n["id"], e["source"])
            assert not (e.get("gas_not_stated") and e.get("gas_stated")), (n["id"], e["source"])
            if not n["air_specific"]:
                continue
            if e.get("gas_not_stated"):
                assert e["direction"] == "context", (n["id"], e["source"])
            elif e["source"] in unstated_sources and e["direction"] != "context":
                assert e.get("gas_stated"), (n["id"], e["source"])


def test_air_specific_flag_covers_the_air_nodes(doc):
    """Every node whose title, quantity or threshold names air, N2/O2, the atmospheric/delivered feed or N/O species is
    flagged air_specific (the flag can be set, but not forgotten, on such a node)."""
    pat = re.compile(r"\bair\b|N2/O2|N2-O2|atmospheric|delivered (feed|composition|air)|\bN/O\b|oxygen|oxidation", re.I)
    for n in doc["nodes"]:
        text = " ".join((n["title"], n["decision_quantity"]["quantity"], n["decision_quantity"]["threshold"]))
        if pat.search(text) and not n.get("sub_cause_of"):
            assert n["air_specific"], n["id"]


def test_review_round2_evidence_relabels(doc):
    nodes = {n["id"]: n for n in doc["nodes"]}

    def item(nid, src):
        return [e for e in nodes[nid]["evidence"] if e["source"] == src]

    for nid in ("N-UTL-02", "N-PWR-02"):
        assert all(e["direction"] == "context" for e in item(nid, "S-SHABSHELOWITZ2014")), nid
        assert nodes[nid]["evidence_status"] == "unknown", nid
    assert all(e["direction"] == "context" for e in item("N-UTL-03", "S-TISAEV2023A"))
    assert all(e["direction"] == "context" for e in item("N-SUS-02", "S-ANDREUSSI2017"))
    for nid in ("N-UTL-03", "N-SUS-02"):
        assert nodes[nid]["evidence_status"] == "unknown", nid


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


_RFP_NUMBER = re.compile(r"12 mN|25 mN|1\.5 kW|1500 W|40 kg|15,000 h|26,000 h|180-230 km")
_ANY_NUMBER_WITH_UNIT = re.compile(r"\b\d[\d,.]*\s*(mN|kW|W|kg|h|km|%|G|T|V|A|sccm|mg/s)\b")


def test_threshold_status_discipline(doc):
    """Every threshold says what it is: a TBD threshold contains 'TBD', a PROPOSED one 'PROPOSED', an RFP one '(RFP)'
    and an RFP number. RFP numbers appear in any threshold only with an 'RFP' label next to them in the same text, and
    no other number with a unit appears in a threshold (non-RFP values are TBD for the owner, never invented)."""
    for n in doc["nodes"]:
        dq = n["decision_quantity"]
        t = dq["threshold"]
        if dq["threshold_status"] == "TBD":
            assert "TBD" in t, n["id"]
        if dq["threshold_status"] == "PROPOSED":
            assert "PROPOSED" in t, n["id"]
        if dq["threshold_status"] == "RFP":
            assert "(RFP)" in t and _RFP_NUMBER.search(t), n["id"]
        if _RFP_NUMBER.search(t):
            assert "RFP" in t, n["id"]
        for m in _ANY_NUMBER_WITH_UNIT.finditer(t):
            assert _RFP_NUMBER.search(m.group(0)) or m.group(0) in ("1.5 kW", "1500 W"), (n["id"], m.group(0))


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
    for arch in ARCHS:                                                 # thermal limit covers the channel walls
        assert any(classes[n["failure_class"]]["name"] == "thermal_limit" and "wall" in n["title"].lower()
                   and arch in n["architectures"] for n in doc["nodes"]), arch
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
    nodes = [n for n in doc["nodes"] if arch in n["architectures"] and n["decision_state"] == "open"
             and not n.get("sub_cause_of")]
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
        mine = [n for n in doc["nodes"] if arch in n["architectures"]]
        assert r["n_nodes"] == sum(1 for n in mine if not n.get("sub_cause_of"))
        assert r["n_sub_causes_not_counted"] == sum(1 for n in mine if n.get("sub_cause_of"))
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


# ------------------------------------------------------------------ review round 2: structure that keeps the counts honest
def test_sub_causes_repeat_their_parent_and_are_not_counted(doc):
    """A sub-cause names an architecture-specific contributor to its parent's threshold comparison. It carries the
    parent's gates and deciding action, says in its threshold that the parent decides it, and is not counted in the
    ranking (so one comparison is never counted twice)."""
    nodes = {n["id"]: n for n in doc["nodes"]}
    subs = [n for n in doc["nodes"] if n.get("sub_cause_of")]
    assert {n["id"] for n in subs} == {"N-MAS-02", "N-MAS-03"}
    for n in subs:
        p = nodes[n["sub_cause_of"]]
        assert not p.get("sub_cause_of"), n["id"]
        assert p["failure_class"] == n["failure_class"], n["id"]
        assert set(n["architectures"]) <= set(p["architectures"]), n["id"]
        assert n["decision_quantity"]["gates"] == p["decision_quantity"]["gates"], n["id"]
        assert p["id"] in n["decision_quantity"]["threshold"], n["id"]
        assert {na["action"] for na in n["actions"]} <= {na["action"] for na in p["actions"]}, n["id"]
    for arch in ARCHS:
        r = doc["ranked_next_evidence"]["per_architecture"][arch]
        for x in r["ranked"]:
            assert not set(x["nodes_decided"] + x["nodes_contributed"] + x["nodes_informed"]) & {n["id"] for n in subs}
        a_mass = [x for x in r["ranked"] if x["action"] == "A-MASS"]
        assert a_mass and a_mass[0]["n_decides"] == 1, arch


def test_unassigned_work_is_named_not_hidden(doc):
    """Work that no lane produces sits in a lane whose deliverable starts with 'TBD - no lane assigned' and is raised
    with the owner; every measurement action is executed by the (unassigned) hardware_test lane and names the lanes
    that only specify it."""
    lanes = {l["id"]: l for l in doc["lanes"]}
    unassigned = {i for i, l in lanes.items() if l["availability"].startswith("not assigned")}
    assert {"mission_ops", "magnetic_interaction", "cathode_oxygen_exposure", "hardware_test"} <= unassigned
    questions = " ".join(doc["open_questions_for_owner"])
    for i in unassigned:
        assert lanes[i]["deliverable"].startswith("TBD - no lane assigned"), i
        assert i in questions, i
    for a in doc["actions"]:
        if a["lane"] in unassigned:
            assert a["deliverable"].startswith(("TBD", "Measurement: TBD")), a["id"]
        if a["kind"] == "measurement":
            assert a["lane"] == "hardware_test", a["id"]
            assert "specified_by" in a, a["id"]
            assert set(a["specified_by"]) <= set(lanes) - unassigned, a["id"]
    acts = {a["id"]: a for a in doc["actions"]}
    assert acts["A-BFIELD"]["lane"] == "magnetic_interaction"
    assert acts["A-OXEXPO"]["lane"] == "cathode_oxygen_exposure"


def test_review_round2_resolution_sets(doc):
    nodes = {n["id"]: n for n in doc["nodes"]}
    # the exposure analysis is part of the jointly sufficient set for poisoning
    assert set(nodes["N-CAT-01"]["cheapest_resolution"]) == {"A-FLOWENV", "A-OXEXPO", "M-CATHODE"}
    # microwave-chain life is not settled by a thermal analysis
    eff = {na["action"]: na["effect"] for na in nodes["N-ECR-03"]["actions"]}
    assert eff["A-THERMAL"] == "informs" and eff["M-MWCHAIN"] == "contributes"
    # no bus-power comparison in the two-stage coupling threshold, so no bus_power gate
    assert "bus_power" not in nodes["N-SUS-03"]["decision_quantity"]["gates"]
    # temperature-limit and plume-mode thresholds compare no power or mass
    for nid in ("N-THM-01", "N-THM-02", "N-THM-03", "N-THM-04", "N-CAT-03"):
        assert nodes[nid]["decision_quantity"]["gates"] == ["firing_life"], nid
    # the ECR/Hall field comparison is stated as frequency-conditional
    assert "MHz" in nodes["N-ECR-02"]["physical_cause"] and "GHz" in nodes["N-ECR-02"]["physical_cause"]


def test_cathode_limit_covers_current_flow_poisoning_and_life(doc):
    """The brief's cathode limits: current, flow, poisoning and life (intrinsic, not only through poisoning)."""
    nodes = {n["id"]: n for n in doc["nodes"]}
    cat = [n for n in doc["nodes"] if n["failure_class"] == "FC-CAT"]
    text = " ".join(n["title"].lower() for n in cat)
    for word in ("current", "flow", "poisoning", "life"):
        assert word in text, word
    assert "firing_life" in nodes["N-CAT-05"]["decision_quantity"]["gates"]
    assert "evaporation" in nodes["N-CAT-05"]["mechanism"].lower()
    assert "Xe-fed" in nodes["N-CAT-06"]["title"]
