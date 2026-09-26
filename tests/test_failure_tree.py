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
                "N-ECR-01", "N-SUS-02", "N-CAT-02", "N-CTL-02",
                # review round 4: a ground thermal-vacuum test predicts flight temperatures only through the correlated
                # thermal network, and nodes on the delivered feed need that feed
                "N-THM-01", "N-THM-02", "N-THM-03", "N-THM-04", "N-CTL-01", "N-SUS-03", "N-RF-02",
                "N-ERO-01", "N-ERO-02", "N-ERO-03", "N-ERO-04", "N-IGN-01"):
        assert not [na for na in nodes[nid]["actions"] if na["effect"] == "decides"], nid


_UNSTATED_GAS = re.compile(r"(gas|composition|propellant)[^.;]{0,60}(not stated|does not state)|"
                          r"(does not state|states no|names neither|states neither)[^.;]{0,40}(gas|composition|propellant)", re.I)
# gas vocabulary: each key is matched as a whole token; aliases count as the same gas
_GAS_ALIASES = {"n2": {"n2", "nitrogen"}, "o2": {"o2", "oxygen"}, "o": {"o", "oxygen"}, "n": {"n", "nitrogen"},
                "nitrogen": {"n2", "nitrogen"}, "oxygen": {"o2", "oxygen"}, "air": {"air"}, "atmospheric": {"atmospheric"},
                "xenon": {"xenon", "xe"}, "xe": {"xenon", "xe"}, "argon": {"argon", "ar"}, "ar": {"argon", "ar"},
                "krypton": {"krypton", "kr"}, "kr": {"krypton", "kr"}}
_ATMOSPHERIC = {"n2", "o2", "o", "n", "nitrogen", "oxygen", "air", "atmospheric"}


def _tokens(text):
    """Word tokens, also splitting chemistry such as '1.27N2+O2' or '0.48O2' into its species."""
    toks = set()
    for t in re.findall(r"[A-Za-z][A-Za-z0-9]*", text):
        toks.add(t.lower())
    toks |= {m.lower() for m in re.findall(r"(?<![A-Za-z])(N2|O2|Xe|Ar|Kr)(?![a-z])", text)}
    return toks


def test_unstated_gas_is_not_decisive_for_air_nodes(doc):
    """Keyed on the substance of each item, not only on its applicability wording (review round 4):
    - every item on an air_specific node declares the gas of its cited result, gas_stated or gas_not_stated (never both);
    - a gas_not_stated item is 'context' there, whatever it reports;
    - a decisive item (supports / contradicts) there carries gas_stated, and that gas must appear in the item's own
      statement or applicability (it cannot be asserted without text behind it);
    - a decisive item whose stated gas names no atmospheric species (e.g. xenon only) must carry a
      gas_independent_rationale, so a different-gas result never decides an air node silently;
    - an applicability text that says the gas is not stated must carry gas_not_stated, on any node."""
    for n in doc["nodes"]:
        assert isinstance(n["air_specific"], bool), n["id"]
        for e in n["evidence"]:
            key = (n["id"], e["source"], e["direction"])
            if _UNSTATED_GAS.search(e["applicability"]):
                assert e.get("gas_not_stated") is True, key
            assert not (e.get("gas_not_stated") and e.get("gas_stated")), key
            if not n["air_specific"]:
                continue
            assert e.get("gas_not_stated") is True or e.get("gas_stated"), ("gas not declared", key)
            if e.get("gas_not_stated"):
                assert e["direction"] == "context", key
                assert not e.get("gas_independent_rationale"), key
                continue
            gas = {t for t in _tokens(e["gas_stated"]) if t in _GAS_ALIASES}
            assert gas, ("gas_stated names no known gas", key, e["gas_stated"])
            text = _tokens(e["statement"] + " " + e["applicability"])
            assert any(_GAS_ALIASES[g] & text for g in gas), ("gas_stated not in the item's text", key, e["gas_stated"])
            if e["direction"] != "context" and not gas & _ATMOSPHERIC:
                assert e.get("gas_independent_rationale", "").strip(), ("different-gas item decides an air node", key)


def test_known_unstated_gas_items_are_context(doc):
    """Review round 4 regressions: items whose source states no gas for the cited result."""
    nodes = {n["id"]: n for n in doc["nodes"]}
    for nid, src in (("N-THM-01", "S-SIMMONDS2022"), ("N-THM-01", "S-MYERS2016"), ("N-THM-04", "S-MYERS2016"),
                     ("N-RF-01", "S-TURNER1999"), ("N-RF-02", "S-ROMANO2020"), ("N-ECR-01", "S-TISAEV2023A")):
        items = [e for e in nodes[nid]["evidence"] if e["source"] == src]
        assert items and all(e.get("gas_not_stated") and e["direction"] == "context" for e in items), (nid, src)
    # both thermal nodes treat S-MYERS2016 the same way, and the paraphrase keeps the components the abstract names
    for nid in ("N-THM-01", "N-THM-04"):
        (m,) = [e for e in nodes[nid]["evidence"] if e["source"] == "S-MYERS2016"]
        assert "(primarily the magnet coils and the discharge channel)" in m["statement"], nid
        assert "xenon" not in m["applicability"].lower() and "verify" in m["applicability"], nid
        assert nodes[nid]["evidence_status"] == "unknown" and nodes[nid].get("evidence_gap"), nid
        overheat = [e for e in nodes[nid]["evidence"] if e["source"] == "S-CIFALI2011" and "overheating" in e["statement"]]
        assert overheat and overheat[0]["direction"] == "context" and overheat[0]["locator"] == "Sec. II.B (pdf p. 4)", nid
    # a xenon result may bear on the ECR cutoff only with its gas-independence stated
    for e in nodes["N-ECR-01"]["evidence"]:
        if e["source"] in ("S-FOSTER2006", "S-DIAMANT2009"):
            assert "frequency" in e["gas_independent_rationale"], e["source"]


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
def _counted(doc, arch, branch=None):
    """Open, non-sub-cause nodes of arch; branch=None gives the core set (no branch), else that option's set."""
    return [n for n in doc["nodes"] if arch in n["architectures"] and n["decision_state"] == "open"
            and not n.get("sub_cause_of") and n.get("branch") == branch]


def _rank_independent(doc, nodes):
    gates_of = {n["id"]: set(n["decision_quantity"]["gates"]) for n in doc["nodes"]}
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
    assert rule["id"] == doc["ranked_next_evidence"]["rule_id"] == "decisiveness_lexicographic_v2"
    assert rule["cost_rank"] == COST
    for arch in ARCHS:
        r = doc["ranked_next_evidence"]["per_architecture"][arch]
        assert [x["action"] for x in r["ranked"]] == _rank_independent(doc, _counted(doc, arch)), arch
        assert [x["rank"] for x in r["ranked"]] == list(range(1, len(r["ranked"]) + 1))
        assert {b["action"] for b in r["blocked"]} <= {"A-HALLMAP"}
        mine = [n for n in doc["nodes"] if arch in n["architectures"]]
        assert r["n_nodes"] == sum(1 for n in mine if not n.get("sub_cause_of") and not n.get("branch"))
        assert r["n_sub_causes_not_counted"] == sum(1 for n in mine if n.get("sub_cause_of"))
        assert r["n_branch_nodes_not_counted"] == sum(1 for n in mine if n.get("branch") and not n.get("sub_cause_of"))
        assert r["ranked"], arch
        expected = [(b["id"], o["id"]) for b in doc["design_branches"] if arch in b["applies_to"] for o in b["options"]]
        assert [(br["decision"], br["option"]) for br in r["branch_rankings"]] == expected, arch
        for br in r["branch_rankings"]:
            bn = _counted(doc, arch, {"decision": br["decision"], "option": br["option"]})
            assert br["n_nodes"] == len(bn), (arch, br["option"])
            assert [x["action"] for x in br["ranked"]] == _rank_independent(doc, bn), (arch, br["option"])


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
def _resolving(n):
    return {(na["action"], na["effect"]) for na in n["actions"] if na["effect"] in ("decides", "contributes")}


def test_sub_causes_repeat_their_parent_and_are_not_counted(doc):
    """A sub-cause repeats its parent's threshold comparison (node_rules.sub_cause_rule). It takes the parent's
    comparison_id, gates, requires_actions, cheapest_resolution and deciding/contributing actions (informs may differ:
    they are not counted), names the parent in its threshold, and is not counted in the ranking, so one comparison is
    never counted twice. The failure class may differ: a sub-cause can be the mechanism behind the parent's quantity."""
    nodes = {n["id"]: n for n in doc["nodes"]}
    subs = [n for n in doc["nodes"] if n.get("sub_cause_of")]
    # regression (review rounds 2-4): the bus comparison at 12 mN, the start-count/start-Xe comparison, the mass total
    assert {"N-MAS-02", "N-MAS-03", "N-UTL-01", "N-PWR-02", "N-PWR-03", "N-PWR-04", "N-CTL-02"} <= {n["id"] for n in subs}
    for n in subs:
        p = nodes[n["sub_cause_of"]]
        pq, q = p["decision_quantity"], n["decision_quantity"]
        assert not p.get("sub_cause_of"), n["id"]
        assert n.get("branch") == p.get("branch"), n["id"]
        assert set(n["architectures"]) <= set(p["architectures"]), n["id"]
        assert q["comparison_id"] == pq["comparison_id"], n["id"]
        assert q["gates"] == pq["gates"], n["id"]
        assert set(q["requires_actions"]) == set(pq["requires_actions"]), n["id"]
        assert n["cheapest_resolution"] == p["cheapest_resolution"], n["id"]
        assert _resolving(n) == _resolving(p), n["id"]
        assert p["id"] in q["threshold"] and "parent" in q["threshold"], n["id"]
    for arch in ARCHS:
        r = doc["ranked_next_evidence"]["per_architecture"][arch]
        for x in r["ranked"]:
            assert not set(x["nodes_decided"] + x["nodes_contributed"] + x["nodes_informed"]) & {n["id"] for n in subs}
        a_mass = [x for x in r["ranked"] if x["action"] == "A-MASS"]
        assert a_mass and a_mass[0]["n_decides"] == 1, arch


def _combinations(doc, arch):
    """Counted node sets of one architecture: the core plus every choice of one option per design branch."""
    import itertools
    decisions = [b for b in doc["design_branches"] if arch in b["applies_to"]]
    for combo in itertools.product(*[[{"decision": b["id"], "option": o["id"]} for o in b["options"]] for b in decisions]):
        yield combo, [n for n in doc["nodes"] if arch in n["architectures"] and n["decision_state"] == "open"
                      and not n.get("sub_cause_of") and (not n.get("branch") or n["branch"] in combo)]


_BUS_AT_12MN = (re.compile(r"\b12 mN\b"), re.compile(r"\b1500 W\b|\b1\.5 kW\b"))


def test_one_comparison_is_counted_once(doc):
    """Counted nodes never share a comparison (node_rules.comparison_rule), checked three ways in every architecture and
    every choice of design-branch options: distinct comparison_id (and a counted node's id follows from its node id, so
    it cannot be made to look distinct by renaming), distinct threshold text, and - on the substance - at most one
    counted node states the RFP bus-power inequality at 12 mN (review round 4 found N-PWR-02/03/04 restating it)."""
    for n in doc["nodes"]:
        if not n.get("sub_cause_of"):
            assert n["decision_quantity"]["comparison_id"] == "CMP-" + n["id"][2:], n["id"]
    for arch in ARCHS:
        for combo, counted in _combinations(doc, arch):
            ids = [n["decision_quantity"]["comparison_id"] for n in counted]
            assert len(ids) == len(set(ids)), (arch, combo)
            thr = [" ".join(n["decision_quantity"]["threshold"].lower().split()) for n in counted]
            assert len(thr) == len(set(thr)), (arch, combo, [t for t in thr if thr.count(t) > 1])
            bus = [n["id"] for n in counted if all(p.search(n["decision_quantity"]["quantity"] + " " +
                                                            n["decision_quantity"]["threshold"]) for p in _BUS_AT_12MN)]
            assert bus == ["N-PWR-01"], (arch, combo, bus)


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
    assert set(nodes["N-CAT-01"]["cheapest_resolution"]) == {"A-FLOWENV", "A-OXEXPO", "M-CATHXE"}
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
    for option, words in (("xe_fed_thermionic", ("current", "flow", "poisoning", "life", "cycle")),
                          ("air_fed_plasma", ("current", "wears out", "cycle"))):
        cat = [n for n in doc["nodes"] if n["failure_class"] == "FC-CAT"
               and n.get("branch") == {"decision": "cathode_feed", "option": option}]
        text = " ".join(n["title"].lower() for n in cat)
        for word in words:
            assert word in text, (option, word)
    assert "firing_life" in nodes["N-CAT-05"]["decision_quantity"]["gates"]
    assert "evaporation" in nodes["N-CAT-05"]["mechanism"].lower()
    assert "Xe-fed" in nodes["N-CAT-06"]["title"]


# ------------------------------------------------------------------ review round 3: design branches and one comparison, one direction
def _branch_options(doc):
    return {(b["id"], o["id"]): b for b in doc["design_branches"] for o in b["options"]}


def test_conditional_nodes_carry_a_declared_branch(doc):
    """A node that applies only under a design choice says so twice: a 'condition' sentence and a machine-readable
    'branch' naming a declared option. Mutually exclusive options are never both counted in one ranking."""
    opts = _branch_options(doc)
    for n in doc["nodes"]:
        assert bool(n.get("condition")) == bool(n.get("branch")), n["id"]
        if n.get("branch"):
            key = (n["branch"]["decision"], n["branch"]["option"])
            assert key in opts, n["id"]
            assert set(n["architectures"]) <= set(opts[key]["applies_to"]), n["id"]
            assert n["branch"]["option"] in n["condition"], n["id"]
    # the Xe-fed cathode nodes are conditional on their branch just like the air-fed alternative (review round 3)
    nodes = {n["id"]: n for n in doc["nodes"]}
    for nid in ("N-CAT-01", "N-CAT-02", "N-CAT-03", "N-CAT-05", "N-CAT-06", "N-CAT-07"):
        assert nodes[nid]["branch"] == {"decision": "cathode_feed", "option": "xe_fed_thermionic"}, nid
    for nid in ("N-CAT-04", "N-CAT-08", "N-CAT-09"):
        assert nodes[nid]["branch"] == {"decision": "cathode_feed", "option": "air_fed_plasma"}, nid
    assert not [n for n in doc["nodes"] if n["failure_class"] == "FC-CAT" and not n.get("branch")]


def test_branch_specific_actions_touch_only_their_branch(doc):
    """An action tied to one option (the Xe-fed or the air-fed cathode test) cannot be credited with nodes of the other
    option or of the core; the old single cathode test that bundled both is gone."""
    acts = {a["id"]: a for a in doc["actions"]}
    assert "M-CATHODE" not in acts
    assert acts["M-CATHXE"]["branch"]["option"] == "xe_fed_thermionic"
    assert acts["M-CATHAIR"]["branch"]["option"] == "air_fed_plasma"
    opts = _branch_options(doc)
    for a in acts.values():
        if a.get("branch"):
            assert (a["branch"]["decision"], a["branch"]["option"]) in opts, a["id"]
    for n in doc["nodes"]:
        for na in n["actions"]:
            b = acts[na["action"]].get("branch")
            if b:
                assert n.get("branch") == b, (n["id"], na["action"])


def test_core_ranking_counts_no_branch_or_sub_cause_node(doc):
    """Guards the counted set, not only the arithmetic: no core row names a branch-specific or sub-cause node, and each
    branch list names only nodes of its own option."""
    nodes = {n["id"]: n for n in doc["nodes"]}
    for arch in ARCHS:
        r = doc["ranked_next_evidence"]["per_architecture"][arch]
        for x in r["ranked"]:
            for nid in x["nodes_decided"] + x["nodes_contributed"] + x["nodes_informed"]:
                assert not nodes[nid].get("branch") and not nodes[nid].get("sub_cause_of"), (arch, x["action"], nid)
        for b in r["blocked"]:
            for nid in b["nodes_touched"]:
                assert not nodes[nid].get("branch") and not nodes[nid].get("sub_cause_of"), (arch, b["action"], nid)
        for br in r["branch_rankings"]:
            want = {"decision": br["decision"], "option": br["option"]}
            for x in br["ranked"]:
                for nid in x["nodes_decided"] + x["nodes_contributed"] + x["nodes_informed"]:
                    assert nodes[nid].get("branch") == want and not nodes[nid].get("sub_cause_of"), (arch, x["action"], nid)


def test_every_branch_combination_covers_every_generic_class_and_gate(doc):
    """Whatever options are chosen, each architecture's tree (core plus the chosen options' nodes) still covers every
    generic failure class and reaches every hard gate."""
    import itertools
    classes = {c["id"]: c["name"] for c in doc["failure_classes"]}
    for arch in ARCHS:
        decisions = [b for b in doc["design_branches"] if arch in b["applies_to"]]
        for combo in itertools.product(*[[(b["id"], o["id"]) for o in b["options"]] for b in decisions]):
            chosen = [{"decision": d, "option": o} for d, o in combo]
            mine = [n for n in doc["nodes"] if arch in n["architectures"] and (not n.get("branch") or n["branch"] in chosen)]
            present = {classes[n["failure_class"]] for n in mine}
            assert GENERIC_CLASSES <= present, (arch, combo, GENERIC_CLASSES - present)
            gates = {g for n in mine for g in n["decision_quantity"]["gates"]}
            assert gates == set(GATES), (arch, combo, set(GATES) - gates)


def test_one_comparison_one_direction_per_source(doc):
    """A source cannot support a failure path on one node and contradict the same threshold comparison on another.
    Nodes are the same comparison when one is a sub-cause of the other, or when their thresholds and gates are equal."""
    nodes = {n["id"]: n for n in doc["nodes"]}
    groups = {}
    for n in doc["nodes"]:
        root = n.get("sub_cause_of") or n["id"]
        groups.setdefault(("parent", root), []).append(n)
        key = ("threshold", n["decision_quantity"]["threshold"], tuple(sorted(n["decision_quantity"]["gates"])))
        groups.setdefault(key, []).append(n)
    for key, members in groups.items():
        by_src = {}
        for n in members:
            for e in n["evidence"]:
                by_src.setdefault(e["source"], set()).add((n["id"], e["direction"]))
        for src, pairs in by_src.items():
            sup = {nid for nid, dr in pairs if dr == "supports"}
            con = {nid for nid, dr in pairs if dr == "contradicts"}
            # conflicting items of one source on one node are allowed (the node is then 'unknown'); across two nodes of one
            # comparison they are not
            assert not any(a != b for a in sup for b in con), (key, src, [m["id"] for m in members])
    # the review-round-3 case: low utilization vs discharge power per thrust within the bus
    assert nodes["N-UTL-01"]["sub_cause_of"] == "N-PWR-01"
    assert nodes["N-UTL-01"]["evidence_status"] == nodes["N-PWR-01"]["evidence_status"] == "contradicted"
    assert not [e for e in nodes["N-UTL-01"]["evidence"] if e["direction"] == "supports"]
    cifali = {e["direction"] for e in nodes["N-UTL-01"]["evidence"] if e["source"] == "S-CIFALI2011"}
    assert cifali == {"context", "contradicts"}


def test_review_round3_applicability_relabels(doc):
    """Support from another regime (a xenon gridded-ion ECR discharge; a DC first stage) is context for the
    RF/ECR-to-Hall nodes, with the gap stated; a comparative physical cause without a source is marked verify."""
    nodes = {n["id"]: n for n in doc["nodes"]}
    for nid, src in (("N-ISL-ECR", "S-FOSTER2006"), ("N-SUS-03", "S-ANDREUSSI2017")):
        items = [e for e in nodes[nid]["evidence"] if e["source"] == src]
        assert items and all(e["direction"] == "context" for e in items), nid
        assert nodes[nid]["evidence_status"] == "unknown" and nodes[nid].get("evidence_gap"), nid
    pc = nodes["N-THM-01"]["physical_cause"]
    assert "verify" in pc and "higher fraction of power lost" not in pc
    # a node whose physical cause is only a hypothesis says so
    for nid in ("N-CAT-07", "N-CAT-09"):
        assert "verify" in nodes[nid]["physical_cause"] and not nodes[nid]["evidence"], nid
    # N-CAT-08 is now carried by S-TISAEV2024 (read in round 4); the life part stays 'verify'
    assert "S-TISAEV2024" in nodes["N-CAT-08"]["physical_cause"] and "verify" in nodes["N-CAT-08"]["physical_cause"]


def test_cifali_operating_point_arithmetic(doc):
    v = {x["id"]: x for x in doc["derived_values"]["values"]}["D-CIFALI-THRUST-N2"]
    assert v["unit"] == "mN" and abs(v["value"] - 305.0 * 3.48 / 41.6) < 1e-3
    assert "verify" in v["note"]


# ------------------------------------------------------------------ review round 4: rules applied the same way everywhere
_DELIVERED = re.compile(r"\bdelivered\b|IF-A5|flow envelope|composition envelope")


def test_delivered_feed_rule(doc):
    """A node evaluated on the delivered feed needs that feed from A-FLOWENV (node_rules.delivered_feed_rule): A-FLOWENV
    is then required (or decides the node). The rule is keyed on the node's own quantity and threshold text."""
    for n in doc["nodes"]:
        dq = n["decision_quantity"]
        if _DELIVERED.search(dq["quantity"] + " " + dq["threshold"]):
            eff = {na["action"]: na["effect"] for na in n["actions"]}
            assert "A-FLOWENV" in dq["requires_actions"] or eff.get("A-FLOWENV") == "decides", n["id"]
    nodes = {n["id"]: n for n in doc["nodes"]}
    for nid in ("N-CTL-01", "N-SUS-03", "N-IGN-01", "N-PWR-01", "N-RF-02"):
        assert "A-FLOWENV" in nodes[nid]["decision_quantity"]["requires_actions"], nid


# what the quantity + threshold must mention for each gate link (hard_gates[].links_when, node_rules.gate_link_rule)
_GATE_WORDS = {
    "thrust": r"thrust|\bmN\b|operating point|design point|setpoint|sustain|acceleration|discharge current|emission current|"
              r"I_emit|ion flux|B\(z\)|transmission|break-even",
    "bus_power": r"\bbus\b|\b\d+ W\b|kW|power|efficiency|reflected",
    "mass": r"\bkg\b|\bmass\b",
    "firing_life": r"firing|\blife\b|temperature|erosion|wear|oxidation|resistance",
    "mission_life": r"\bmission\b|off periods?\b|calendar|deplet",
    "restart_sustainment": r"start|sustain|extinction|oscillation|regulation|breakdown|ignit|\btrips?\b|\bmode\b|B\(z\)|"
                           r"resonance|continuity|pressure reached",
    "air_xe": r"\bXe\b|xenon|noble|air_xe",
}


def test_gate_links_match_what_the_threshold_compares(doc):
    """A node links only gates whose criterion its threshold compares. Checked on the text: each linked gate's
    vocabulary appears in the node's quantity or threshold (review round 4: start-count thresholds had linked firing
    and mission life). Every gate states what a link to it means."""
    for g in doc["hard_gates"]:
        assert g["links_when"].strip(), g["id"]
    for n in doc["nodes"]:
        dq = n["decision_quantity"]
        text = dq["quantity"] + " " + dq["threshold"]
        for gate in dq["gates"]:
            assert re.search(_GATE_WORDS[gate], text, re.I), (n["id"], gate)
    nodes = {n["id"]: n for n in doc["nodes"]}
    for nid in ("N-CAT-07", "N-CAT-09"):                       # start cycles: restart only
        assert nodes[nid]["decision_quantity"]["gates"] == ["restart_sustainment"], nid
    for nid in ("N-IGN-01", "N-CTL-02"):                       # start success and start Xe (consumable depletion)
        assert not {"firing_life", "mass"} & set(nodes[nid]["decision_quantity"]["gates"]), nid
    # the proposed cathode gate is 'cathode life and start cycles': not Xe mass, not current
    for n in doc["nodes"]:
        if "P2_cathode" in n.get("proposed_gate_links", []):
            assert {"firing_life", "restart_sustainment"} & set(n["decision_quantity"]["gates"]), n["id"]
    for nid in ("N-CAT-02", "N-CAT-04", "N-CAT-06"):
        assert "P2_cathode" not in nodes[nid].get("proposed_gate_links", []), nid


def _set_key(acts, s):
    return (max(COST[acts[a]["kind"]] for a in s), len(s), tuple(sorted(s)))


def test_cheapest_resolution_tie_break(doc):
    """cheapest_resolution is the minimum of (highest cost class, number of actions, sorted ids) over the unblocked
    deciding actions, itself and the listed alternative_resolutions; every contributing action belongs to one of those
    sets, so no jointly sufficient set is chosen by hand (review round 4: N-IGN-02 vs N-IGN-03)."""
    acts = {a["id"]: a for a in doc["actions"]}
    for n in doc["nodes"]:
        eff = {na["action"]: na["effect"] for na in n["actions"]}
        alts = n.get("alternative_resolutions", [])
        for s in alts:
            assert all(eff.get(a) == "contributes" and not acts[a]["blocked_by"] for a in s), (n["id"], s)
            assert set(n["decision_quantity"]["requires_actions"]) <= set(s), (n["id"], s)
        cands = [[a] for a, e in eff.items() if e == "decides" and not acts[a]["blocked_by"]] + [n["cheapest_resolution"]] + alts
        best = min(cands, key=lambda s: _set_key(acts, s))
        assert sorted(best) == sorted(n["cheapest_resolution"]), (n["id"], best)
        covered = set().union(*[set(s) for s in [n["cheapest_resolution"]] + alts])
        for a, e in eff.items():
            if e == "contributes":
                assert a in covered, (n["id"], a)


def test_physical_cause_basis(doc):
    """Every physical cause says what carries it: cited ids (which must exist), a ledger/budget definition, or a
    hypothesis marked 'verify' (review round 4: N-RF-04, N-ECR-03, N-ERO-04 and N-THM-02 were unmarked)."""
    src = {s["id"] for s in doc["sources"]}
    dv = {v["id"] for v in doc["derived_values"]["values"]}
    for n in doc["nodes"]:
        pc, basis = n["physical_cause"], n["physical_cause_basis"]
        ids = re.findall(r"\b([SD]-[A-Z0-9][A-Z0-9.-]*[A-Z0-9])", pc)
        for i in ids:
            assert i in src or i in dv, (n["id"], i)
        if basis == "cited":
            assert ids, n["id"]
        elif basis == "hypothesis":
            assert "verify" in pc, n["id"]
        else:
            assert basis == "definition" and "identity" in pc, n["id"]
    nodes = {n["id"]: n for n in doc["nodes"]}
    for nid in ("N-RF-04", "N-ECR-03", "N-THM-02"):
        assert nodes[nid]["physical_cause_basis"] == "hypothesis", nid


def test_review_round4_evidence_and_citations(doc):
    nodes = {n["id"]: n for n in doc["nodes"]}
    src = {s["id"]: s for s in doc["sources"]}
    acts = {a["id"]: a for a in doc["actions"]}
    # the SITAEL follow-up is AIAA 2019-3995 (10.2514/6.2019-3996 is an iodine feed-system paper)
    assert "AIAA 2019-3995" in acts["L-SITAEL"]["description"] and "3996" not in acts["L-SITAEL"]["description"]
    assert src["S-ANDREUSSI2019"]["doi"] == "10.2514/6.2019-3995"
    assert "Molecular Propellant" in src["S-BRABSTON2025"]["citation"] and "41(6)" in src["S-BRABSTON2025"]["citation"]
    assert "(2007)" in src["S-GOEBEL2007"]["citation"] and "23(3)" in src["S-GOEBEL2007"]["citation"]
    assert src["S-ROMANO2020"]["doi"] == "10.1016/j.actaastro.2020.07.008"
    # the thermal test predicts flight temperatures only with the correlated network: it never decides alone
    for n in doc["nodes"]:
        for na in n["actions"]:
            if na["action"] == "M-THERMAL":
                assert na["effect"] == "contributes", n["id"]
                assert {"effect": "contributes", "action": "A-THERMAL"} in n["actions"], n["id"]
    # one direction label per regime: relative or magnitude statements on the air-fed cathode current are context
    assert all(e["direction"] == "context" for e in nodes["N-CAT-04"]["evidence"])
    # a matched air flow range covers one leg of the N-RF-02 disjunction only
    assert all(e["direction"] == "context" for e in nodes["N-RF-02"]["evidence"])
    assert nodes["N-RF-02"]["evidence_status"] == "unknown"
    # S-TISAEV2024 read in full: air-plasma antenna sputtering and coating (supports), mitigation over hours (context)
    assert src["S-TISAEV2024"]["access"] == "full_text_open" and "sha256" in src["S-TISAEV2024"]
    for nid in ("N-CAT-08", "N-ERO-04"):
        dirs = {e["direction"] for e in nodes[nid]["evidence"] if e["source"] == "S-TISAEV2024"}
        assert dirs == {"supports", "context"} and nodes[nid]["evidence_status"] == "supported", nid
        assert nodes[nid].get("status_note"), nid
    # 'supported' on an intrinsic-life mechanism is not a life verdict
    assert "50,000" in nodes["N-CAT-05"]["status_note"] and "does not mean" in nodes["N-CAT-05"]["status_note"]
    # the interstage model is unvalidated: it informs, never contributes
    for n in doc["nodes"]:
        for na in n["actions"]:
            if na["action"] == "A-INTERSTAGE":
                assert na["effect"] == "informs", n["id"]
