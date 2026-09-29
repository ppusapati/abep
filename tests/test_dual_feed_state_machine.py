"""Structural and evidence-discipline checks of the dual-feed (Xe + atmosphere) operational state machine,
schemas/controls/dual_feed_state_machine_v1.json (rationale: docs/controls/DUAL_FEED_STATES.md).

These tests check the control-logic graph and its bookkeeping only: reachability, safing, required transition fields,
symbolic guards and the absence of unsourced numbers. They assert nothing about discharge physics, and they import no
simulator module (simulator references are resolved by parsing the source with `ast`).

The machine is parameterised over the three thrust architectures (hall_only, rf_hall, ecr_hall) and the pre-ionizer
start variants (V1 after discharge, V2 seed before discharge); every graph property is checked per configuration.
Modules owned by other lanes (abep_sim.arch_boundary, abep_sim.cathode_integration) are resolved lazily: when the file is
absent from the checkout the reference is skipped, when present it must resolve and agree with this specification.
"""
from __future__ import annotations

import ast
import json
import os
import re
from collections import deque

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SM_FILE = os.path.join(ROOT, "schemas", "controls", "dual_feed_state_machine_v1.json")
DOC_FILE = os.path.join(ROOT, "docs", "controls", "DUAL_FEED_STATES.md")
ENSEMBLE_FILE = os.path.join(ROOT, "hallthruster_bridge", "ensemble", "transport_ensemble_v0.json")

REQUIRED_STATES = {
    "OFF", "XE_PURGE", "CATHODE_CONDITIONING", "CATHODE_IGNITION", "XE_DISCHARGE_IGNITION", "WARM_UP",
    "ATMOSPHERE_ADMISSION", "MIXED_STABILIZATION", "ATMOSPHERE_DOMINANT", "AIR_ONLY_ANODE_XE_CATHODE",
    "DEGRADED_OPERATION", "XE_FALLBACK", "CONTROLLED_SHUTDOWN", "RESTART", "SAFE_MODE",
}
REQUIRED_CATEGORIES = ("pressure", "discharge_current", "flows", "timing", "power")
TRANSITION_FIELDS = ("id", "from", "to", "kind", "trigger", "guard_logic", "preconditions", "guards", "actions",
                     "fault_behaviour", "xe_consumed", "rationale")
FAULT_BEHAVIOUR_FIELDS = ("on_fault", "fault_transition", "on_guard_not_met", "description")
KINDS = {"nominal", "retry", "command", "degradation", "recovery", "protective", "fault"}
LOGICS = {"ALL", "ANY_PERSISTING"}
EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
SUPPLIER_STATUSES = {"available", "input_only", "component_only", "proxy_not_equivalent", "gated", "withdrawn_absolute",
                     "superseded_do_not_use"}
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
# bus_power_boundary_v1 pre-ionizer components (the contract of abep_sim/arch_boundary.py, lane_11_bus_boundary)
PREIONIZER_COMPONENTS = {"hall_only": [], "rf_hall": ["rf_source"], "ecr_hall": ["ecr_source", "ecr_magnet"]}
CONFIG_IDS = {"hall_only", "rf_hall/V1", "rf_hall/V2", "ecr_hall/V1", "ecr_hall/V2"}
PREIONIZER_STATES = {"PREIONIZER_SEED", "PREIONIZER_IGNITION"}
OUTPUT_KEYS = {"anode_hv", "keeper", "heater", "magnet", "preionizer"}
# power symbols allowed in guards: P_bus family of bus_power_boundary_v1, plus the cathode heater component guard
POWER_SYMBOLS = {"P_bus", "P_bus_demand", "P_bus_avail", "P_bus_alloc", "P_bus_min_sustain", "P_bus_idle_max",
                 "P_startup_peak", "P_heater", "P_heater_max"}
TBD = "TBD — requires "
KEYWORDS = {"AND", "OR", "NOT", "abs", "integral"}
OPERATORS = {"<", "<=", ">", ">=", "==", "!=", "+", "-", "*", "/", "(", ")", ","}
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|<=|>=|==|!=|\S")
NUMERIC_LITERAL = re.compile(r"(?<![A-Za-z0-9_])\d")
# the superseded 0-D Hall closure (CLAUDE.md "Superseded / withdrawn"): never a guard-quantity supplier
ZERO_D_HALL = {"hall_run_coupled", "hall_discharge_transient", "hall_fixed_points", "HallChannel", "coupled_channel"}


@pytest.fixture(scope="module")
def sm() -> dict:
    with open(SM_FILE, encoding="utf-8") as f:
        return json.load(f)


def _states(sm):
    return {s["id"]: s for s in sm["states"]}


def _graph(sm, cfg=None):
    """Transition graph, projected onto configuration ``cfg`` when given."""
    g = {sid: set() for sid, s in _states(sm).items() if cfg is None or cfg in s["applies_to"]}
    for t in sm["transitions"]:
        if cfg is None or cfg in t["applies_to"]:
            g[t["from"]].add(t["to"])
    return g


def _configs(sm):
    return [c["id"] for c in sm["configurations"]]


def _variant(sm, cfg):
    return next(c["start_variant"] for c in sm["configurations"] if c["id"] == cfg)


def _reach(g, start):
    seen, todo = {start}, deque([start])
    while todo:
        for nxt in g[todo.popleft()]:
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def _is_special(text: str) -> bool:
    return text.startswith("n/a:") or text.startswith("none:") or text.startswith(TBD)


def _expressions(sm):
    """(where, expression) for every machine-evaluable expression in the file."""
    out = []
    for s in sm["states"]:
        out.append((f"state {s['id']} xe_rate", s["xe_rate"]))
        out += [(f"state {s['id']} invariant", e) for e in s["invariants"]]
    for t in sm["transitions"]:
        out += [(f"{t['id']} precondition", e) for e in t["preconditions"]]
        for cat, entries in t["guards"].items():
            out += [(f"{t['id']} guard {cat}", e) for e in entries]
        out += [(f"{t['id']} xe_consumed {k}", v) for k, v in t["xe_consumed"].items()]
    out += [("parameter_constraints", e) for e in sm["parameter_constraints"]]
    out += [("global_invariants", e) for e in sm["global_invariants"]]
    return out


def _free_text_actions(sm):
    out = []
    for s in sm["states"]:
        out += [(f"state {s['id']} entry action", a) for a in s["entry_actions"]]
    for t in sm["transitions"]:
        out += [(f"{t['id']} action", a) for a in t["actions"]]
    return out


def _identifiers(expr: str) -> list[str]:
    return [tok for tok in TOKEN.findall(expr) if re.match(r"[A-Za-z_]", tok)]


def _resolve(ref: str) -> bool:
    """True if 'package.module:Name[.attr]' names a top-level def/class/assignment (and nested member) in the source."""
    mod, _, qual = ref.partition(":")
    path = os.path.join(ROOT, *mod.split(".")) + ".py"
    if not qual or not os.path.isfile(path):
        return False
    return _resolve_in(path, qual)


def _other_lane_absent(sm, ref: str) -> bool:
    mod = ref.partition(":")[0]
    info = sm["other_lane_modules"].get(mod)
    return info is not None and not os.path.isfile(os.path.join(ROOT, info["path"]))


def _resolve_in(path: str, qual: str) -> bool:
    with open(path, encoding="utf-8") as f:
        body = ast.parse(f.read()).body
    for name in qual.split("."):
        found = None
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
                found = node
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
                found = node
            elif isinstance(node, ast.Assign) and any(isinstance(x, ast.Name) and x.id == name for x in node.targets):
                found = node
        if found is None:
            return False
        body = getattr(found, "body", [])
    return True


# ------------------------------------------------------------------------------------------------ structure

def test_header(sm):
    assert sm["schema"] == "dual_feed_state_machine_v1"
    assert sm["status"] == "DRAFT"
    assert set(sm["evidence_classes"]) == EVIDENCE_CLASSES
    assert sm["tbd_prefix"] == TBD
    assert tuple(sm["required_guard_categories"]) == REQUIRED_CATEGORIES
    assert sm["initial_state"] == "OFF"


def test_required_states_present_and_unique(sm):
    ids = [s["id"] for s in sm["states"]]
    assert len(ids) == len(set(ids)), "duplicate state id"
    assert REQUIRED_STATES <= set(ids), f"missing states: {sorted(REQUIRED_STATES - set(ids))}"
    states = _states(sm)
    for sid in sm["safe_states"] + sm["safing_states"] + [sm["initial_state"]]:
        assert sid in states
    assert not set(sm["safe_states"]) & set(sm["safing_states"])


def test_state_fields(sm):
    for s in sm["states"]:
        for k in ("category", "safe", "terminal", "description", "outputs", "valves", "compressor", "xe_rate",
                  "entry_actions", "invariants", "rationale"):
            assert k in s, f"state {s['id']} missing {k}"
        assert s["safe"] == (s["id"] in sm["safe_states"]), s["id"]
        assert set(s["valves"]) == {"xe_cathode", "xe_anode", "atm_anode"}, s["id"]
        assert set(s["outputs"]) == OUTPUT_KEYS, s["id"]
        pre = s["outputs"]["preionizer"]
        assert isinstance(pre, dict) and set(pre) == {"none", "V1", "V2"}, f"{s['id']}: preionizer output per start variant"
        assert pre["none"].startswith("absent"), f"{s['id']}: hall_only has no pre-ionizer"
        assert s["applies_to"] and set(s["applies_to"]) <= CONFIG_IDS, s["id"]


def test_every_transition_has_required_fields(sm):
    states = _states(sm)
    ids = [t["id"] for t in sm["transitions"]]
    assert len(ids) == len(set(ids)), "duplicate transition id"
    allowed_cats = set(REQUIRED_CATEGORIES) | set(sm["optional_guard_categories"])
    for t in sm["transitions"]:
        for k in TRANSITION_FIELDS:
            assert k in t, f"{t.get('id')} missing {k}"
        assert t["from"] in states and t["to"] in states, t["id"]
        assert t["applies_to"] and set(t["applies_to"]) <= CONFIG_IDS, t["id"]
        assert set(t["applies_to"]) <= set(states[t["from"]]["applies_to"]) & set(states[t["to"]]["applies_to"]), \
            f"{t['id']} applies to a configuration in which its source or target state does not exist"
        assert t["kind"] in KINDS, t["id"]
        assert t["guard_logic"] in LOGICS, t["id"]
        assert isinstance(t["rationale"], str) and t["rationale"].strip(), t["id"]
        g = t["guards"]
        for cat in REQUIRED_CATEGORIES:
            assert cat in g, f"{t['id']}: guard category {cat} missing (use 'n/a: <reason>' when it imposes nothing)"
        assert set(g) <= allowed_cats, f"{t['id']}: unknown guard categories {sorted(set(g) - allowed_cats)}"
        for cat, entries in g.items():
            assert isinstance(entries, list) and entries, f"{t['id']}: {cat} must be a non-empty list"
            for e in entries:
                assert isinstance(e, str) and e.strip(), f"{t['id']}: {cat} entry"
                if e.startswith("n/a:"):
                    assert e[len("n/a:"):].strip(), f"{t['id']}: {cat} 'n/a:' needs a reason"
        assert all(isinstance(e, str) and e.strip() for e in t["preconditions"]), t["id"]
        assert all(isinstance(a, str) and a.strip() for a in t["actions"]), t["id"]
        for k in FAULT_BEHAVIOUR_FIELDS:
            assert k in t["fault_behaviour"], f"{t['id']}: fault_behaviour.{k} missing"
        assert set(t["xe_consumed"]) == {"in_source_state", "at_transition"}, t["id"]
        if t["guard_logic"] == "ANY_PERSISTING":
            timing = [e for e in g["timing"] if not e.startswith("n/a:")]
            assert timing and all("t_condition" in e for e in timing), f"{t['id']}: persistence must be on t_condition"
            triggers = [e for c, es in g.items() if c != "timing" for e in es if not e.startswith("n/a:")]
            assert triggers, f"{t['id']}: ANY_PERSISTING transition without a trigger condition"


def test_nominal_and_recovery_transitions_are_time_qualified(sm):
    for t in sm["transitions"]:
        if t["kind"] in ("nominal", "recovery", "retry"):
            assert any(not e.startswith("n/a:") for e in t["guards"]["timing"]), f"{t['id']} has no timing condition"


# ------------------------------------------------------------------------------------------------ graph properties

def test_configurations_cover_the_three_architectures(sm):
    cfgs = sm["configurations"]
    assert {c["id"] for c in cfgs} == CONFIG_IDS
    assert {c["architecture"] for c in cfgs} == set(ARCHITECTURES) == set(sm["architecture_context"]["architectures"])
    for c in cfgs:
        assert c["preionizer_boundary_components"] == PREIONIZER_COMPONENTS[c["architecture"]], c["id"]
        assert c["start_variant"] == ("none" if c["architecture"] == "hall_only" else c["id"].split("/")[1]), c["id"]
        assert c["start_variant"] in sm["preionizer_start_variants"], c["id"]
    assert sm["preionizer_start_variants"]["status"].startswith("OPEN")


def test_every_state_reachable_from_off(sm):
    for cfg in _configs(sm):
        g = _graph(sm, cfg)
        assert REQUIRED_STATES <= set(g), f"{cfg}: missing required states {sorted(REQUIRED_STATES - set(g))}"
        reach = _reach(g, sm["initial_state"])
        assert set(g) <= reach, f"{cfg}: unreachable from OFF: {sorted(set(g) - reach)}"


def test_every_non_terminal_state_has_path_to_safe_state(sm):
    safe = set(sm["safe_states"])
    for cfg in _configs(sm):
        g = _graph(sm, cfg)
        for sid in g:
            if _states(sm)[sid]["safe"]:
                continue
            assert _reach(g, sid) & safe, f"{cfg}: {sid} has no path to a safe state"


def test_every_non_safe_state_has_direct_fault_exit_to_safe_mode(sm):
    for cfg in _configs(sm):
        for sid in _graph(sm, cfg):
            if sid == "SAFE_MODE":
                continue
            faults = [t for t in sm["transitions"] if t["from"] == sid and t["kind"] == "fault" and cfg in t["applies_to"]]
            assert faults, f"{cfg}: {sid} has no fault transition"
            assert any(t["to"] == "SAFE_MODE" for t in faults), f"{cfg}: {sid}: no fault transition to SAFE_MODE"


def test_preionizer_states_gate_atmosphere_admission(sm):
    """hall_only never enters a pre-ionizer state; rf_hall/ecr_hall reach atmosphere admission only through
    PREIONIZER_IGNITION, and V2 reaches anode ignition only through PREIONIZER_SEED."""
    for cfg in _configs(sm):
        g = _graph(sm, cfg)
        v = _variant(sm, cfg)
        if v == "none":
            assert not PREIONIZER_STATES & set(g), cfg
            continue
        assert "PREIONIZER_IGNITION" in g, cfg
        assert ("PREIONIZER_SEED" in g) == (v == "V2"), cfg
        cut = {k: {x for x in nxt if x != "PREIONIZER_IGNITION"} for k, nxt in g.items() if k != "PREIONIZER_IGNITION"}
        assert "ATMOSPHERE_ADMISSION" not in _reach(cut, sm["initial_state"]), f"{cfg}: admission bypasses PREIONIZER_IGNITION"
        if v == "V2":
            cut = {k: {x for x in nxt if x != "PREIONIZER_SEED"} for k, nxt in g.items() if k != "PREIONIZER_SEED"}
            assert "XE_DISCHARGE_IGNITION" not in _reach(cut, sm["initial_state"]), f"{cfg}: V2 ignition bypasses the seed"


def test_preionizer_loss_and_faults_are_handled(sm):
    """Where a configuration's pre-ionizer is energised, a hard pre-ionizer fault leads to SAFE_MODE; in the
    atmospheric/mixed operating states a pre-ionizer loss leads to XE_FALLBACK."""
    states = _states(sm)
    for cfg in _configs(sm):
        v = _variant(sm, cfg)
        if v == "none":
            continue
        for sid in _graph(sm, cfg):
            out = states[sid]["outputs"]["preionizer"][v]
            if out == "off":
                continue
            outs = [t for t in sm["transitions"] if t["from"] == sid and cfg in t["applies_to"]]
            assert any(t["kind"] == "fault" and t["to"] == "SAFE_MODE" and "preionizer_fault" in " ".join(t["guards"].get("health", []))
                       for t in outs), f"{cfg}: {sid} energises the pre-ionizer without a pre-ionizer fault exit"
            if states[sid]["category"] in ("operating", "degraded") and sid != "XE_FALLBACK":
                assert any(t["to"] == "XE_FALLBACK" and "NOT preionizer_lit" in t["guards"].get("health", []) for t in outs), \
                    f"{cfg}: {sid} has no pre-ionizer loss handling"


def test_power_guards_use_the_bus_power_boundary(sm):
    """Power guards use P_bus of bus_power_boundary_v1 (OPERATING_MODEL section 3), never a narrower definition."""
    pb = sm["power_boundary"]
    assert pb["boundary_version"] == "bus_power_boundary_v1" and pb["quantity"] == "P_bus"
    assert pb["contract"]["module"] == "abep_sim.arch_boundary" and pb["contract"]["function"] == "bus_power_ledger"
    for name in ("P_bus", "P_bus_demand"):
        q = sm["quantities"][name]
        assert q["boundary_version"] == "bus_power_boundary_v1", name
        assert any(s["ref"] == "abep_sim.arch_boundary:bus_power_ledger" and s["status"] == "available"
                   for s in q["simulator_suppliers"]), f"{name}: the boundary ledger must be its supplier"
        for s in q["simulator_suppliers"]:
            if s["ref"] != "abep_sim.arch_boundary:bus_power_ledger":
                assert s["status"] in ("component_only", "input_only"), f"{name}: {s['ref']} would substitute for P_bus"
    assert "P_bus <= P_bus_alloc" in sm["global_invariants"]
    assert "P_bus_alloc <= RFP_power_max" in sm["parameter_constraints"]
    for where, e in _expressions(sm):
        if _is_special(e):
            continue
        for tok in _identifiers(e):
            assert "P_prop" not in tok and "P_avail" not in tok, f"legacy power symbol {tok!r} in {where}"
            if tok.startswith("P_") and tok in set(sm["quantities"]) | set(sm["parameters"]):
                assert tok in POWER_SYMBOLS, f"power symbol {tok!r} outside the bus_power_boundary_v1 family in {where}"
    if os.path.isfile(os.path.join(ROOT, "abep_sim", "arch_boundary.py")):
        with open(os.path.join(ROOT, "abep_sim", "arch_boundary.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        consts = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try:
                    consts[node.targets[0].id] = ast.literal_eval(node.value)
                except ValueError:
                    pass
        assert consts["BOUNDARY_VERSION"] == pb["boundary_version"]
        assert tuple(consts["ARCHITECTURES"]) == ARCHITECTURES
        assert {k: list(v) for k, v in consts["PREIONIZER_COMPONENTS"].items()} == PREIONIZER_COMPONENTS


def test_safing_states_only_exit_to_safe_states(sm):
    safe = set(sm["safe_states"])
    for sid in sm["safing_states"]:
        outs = [t for t in sm["transitions"] if t["from"] == sid]
        assert outs, f"safing state {sid} has no exit"
        assert all(t["to"] in safe for t in outs), f"{sid} can re-enter operation"


def _ends_safe(sm, target: str) -> bool:
    safe = set(sm["safe_states"])
    if target in safe:
        return True
    if target in sm["safing_states"]:
        return all(t["to"] in safe for t in sm["transitions"] if t["from"] == target)
    return False


def test_every_fault_transition_ends_in_safe_state(sm):
    for t in sm["transitions"]:
        if t["kind"] == "fault":
            assert t["to"] in sm["safe_states"], f"fault transition {t['id']} does not go to a safe state"
        if t["kind"] in ("fault", "protective"):
            assert _ends_safe(sm, t["to"]), f"{t['id']} ({t['kind']}) does not end in a safe state"
        if t["kind"] == "command" and t["to"] in sm["safing_states"] + sm["safe_states"]:
            assert _ends_safe(sm, t["to"]), t["id"]


def test_fault_behaviour_is_consistent(sm):
    by_id = {t["id"]: t for t in sm["transitions"]}
    for t in sm["transitions"]:
        fb = t["fault_behaviour"]
        assert _ends_safe(sm, fb["on_fault"]), f"{t['id']}: on_fault {fb['on_fault']} is not safe"
        ft = fb["fault_transition"]
        if not ft.startswith("n/a:"):
            assert ft in by_id, f"{t['id']}: unknown fault_transition {ft}"
            assert by_id[ft]["kind"] == "fault" and by_id[ft]["from"] == t["from"], f"{t['id']}: bad fault_transition {ft}"
        else:
            assert t["from"] == "SAFE_MODE", f"{t['id']}: only SAFE_MODE may lack a fault transition"
        nm = fb["on_guard_not_met"]
        if not nm.startswith("n/a:"):
            assert nm in by_id and by_id[nm]["from"] == t["from"], f"{t['id']}: on_guard_not_met {nm} must leave the same state"


def test_safe_states_are_de_energised(sm):
    for sid in sm["safe_states"]:
        s = _states(sm)[sid]
        assert {v for k, v in s["outputs"].items() if k != "preionizer"} == {"off"}, sid
        pre = s["outputs"]["preionizer"]
        assert pre["V1"] == pre["V2"] == "off" and pre["none"].startswith("absent"), sid
        assert set(s["valves"].values()) == {"closed"}, sid
        assert s["compressor"] == "off", sid
        assert s["xe_rate"].startswith("none:"), sid


def test_retry_loops_are_bounded(sm):
    for t in sm["transitions"]:
        if t["kind"] != "retry":
            continue
        assert t["from"] == t["to"], f"{t['id']}: retry must be a self-loop"
        bounds = [re.fullmatch(r"(n_\w+) < (n_\w+_max)", e) for e in t["preconditions"]]
        bounds = [b for b in bounds if b]
        assert bounds, f"{t['id']}: retry without a counter bound"
        counter, limit = bounds[0].groups()
        assert any(counter in a for a in t["actions"]), f"{t['id']}: counter {counter} not incremented"
        exhausted = [u for u in sm["transitions"] if u["from"] == t["from"] and u["kind"] == "protective"
                     and f"{counter} >= {limit}" in u["preconditions"]]
        assert exhausted and all(_ends_safe(sm, u["to"]) for u in exhausted), f"{t['id']}: no safe exit when retries are exhausted"


def test_xe_ledger_matches_state_rates(sm):
    states = _states(sm)
    for t in sm["transitions"]:
        rate = states[t["from"]]["xe_rate"]
        got = t["xe_consumed"]["in_source_state"]
        if rate.startswith("none:"):
            assert got.startswith("none:"), t["id"]
        else:
            assert got == f"integral({rate}, t_in_state)", t["id"]
    for sid in ("AIR_ONLY_ANODE_XE_CATHODE",):
        assert states[sid]["xe_rate"] == "mdot_Xe_cathode"
        assert states[sid]["valves"]["xe_anode"] == "closed"


# ------------------------------------------------------------------------------------------------ evidence discipline

def test_parameter_values_are_tbd_or_sourced(sm):
    assert sm["parameters"], "no parameters"
    for name, p in sm["parameters"].items():
        for k in ("unit", "description", "value", "source", "evidence_class"):
            assert k in p, f"parameter {name} missing {k}"
        v = p["value"]
        if isinstance(v, str):
            assert v.startswith(TBD) and v[len(TBD):].strip(), f"parameter {name}: value must be '{TBD}<what>' or sourced"
        else:
            assert isinstance(v, (int, float)) and not isinstance(v, bool), f"parameter {name}: bad value type"
            assert isinstance(p["source"], str) and p["source"].strip(), f"parameter {name}: numeric value without source"
            assert p["evidence_class"] in EVIDENCE_CLASSES, f"parameter {name}: numeric value without evidence class"


def test_no_numbers_outside_sourced_parameters(sm):
    """Any JSON number must be a parameter value that carries a source and an evidence class."""
    bad = []

    def walk(node, path):
        if isinstance(node, bool) or node is None or isinstance(node, str):
            return
        if isinstance(node, (int, float)):
            ok = (len(path) == 3 and path[0] == "parameters" and path[2] == "value"
                  and sm["parameters"][path[1]].get("source") and sm["parameters"][path[1]].get("evidence_class") in EVIDENCE_CLASSES)
            if not ok:
                bad.append("/".join(map(str, path)))
            return
        items = node.items() if isinstance(node, dict) else enumerate(node)
        for k, v in items:
            walk(v, path + [k])

    walk(sm, [])
    assert not bad, f"unsourced numbers at {bad}"


def test_no_numeric_literals_in_guards_or_actions(sm):
    for where, e in _expressions(sm) + _free_text_actions(sm):
        if _is_special(e):
            continue
        assert not NUMERIC_LITERAL.search(e), f"numeric literal in {where}: {e!r} (name it as a parameter)"


def test_expression_symbols_are_declared(sm):
    declared = set(sm["quantities"]) | set(sm["parameters"]) | set(sm["external_refs"])
    assert not set(sm["quantities"]) & set(sm["parameters"]), "a name is both quantity and parameter"
    for where, e in _expressions(sm):
        if _is_special(e):
            continue
        for tok in TOKEN.findall(e):
            if re.match(r"[A-Za-z_]", tok):
                assert tok in KEYWORDS or tok in declared, f"undeclared symbol {tok!r} in {where}: {e!r}"
            else:
                assert tok in OPERATORS, f"unexpected token {tok!r} in {where}: {e!r}"


def _used_names(sm) -> set[str]:
    used = set()
    for _, e in _expressions(sm):
        if not _is_special(e):
            used |= set(_identifiers(e))
    text = " ".join(a for _, a in _free_text_actions(sm))
    used |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text))
    for q in sm["quantities"].values():
        used |= set(q.get("depends_on_parameters", []))
    return used


def test_every_parameter_and_quantity_is_used(sm):
    used = _used_names(sm)
    unused_p = sorted(set(sm["parameters"]) - used)
    unused_q = sorted(set(sm["quantities"]) - used)
    assert not unused_p, f"parameters never used: {unused_p}"
    assert not unused_q, f"quantities never used: {unused_q}"
    for name, q in sm["quantities"].items():
        for p in q.get("depends_on_parameters", []):
            assert p in sm["parameters"], f"quantity {name} depends on undeclared parameter {p}"


def test_simulator_references_exist(sm):
    refs = []
    for name, q in sm["quantities"].items():
        for s in q["simulator_suppliers"]:
            assert s["status"] in SUPPLIER_STATUSES, f"{name}: status {s['status']}"
            assert s["output"].strip(), name
            refs.append((f"quantity {name}", s["ref"]))
    for name, p in sm["parameters"].items():
        refs += [(f"parameter {name}", r) for r in p.get("determined_by", [])]
    refs += [(f"external_ref {k}", v["ref"]) for k, v in sm["external_refs"].items()]
    missing = [(w, r) for w, r in refs if not _other_lane_absent(sm, r) and not _resolve(r)]
    assert not missing, f"references to non-existent simulator code: {missing}"
    for name, q in sm["quantities"].items():
        for s in q["simulator_suppliers"]:
            if s["ref"].partition(":")[0] in sm["other_lane_modules"]:
                assert s.get("lazy") is True, f"{name}: other-lane supplier {s['ref']} must be marked lazy"


def test_quantities_without_an_available_supplier_state_the_gap(sm):
    for name, q in sm["quantities"].items():
        for k in ("unit", "kind", "description", "telemetry", "simulator_suppliers"):
            assert k in q, f"quantity {name} missing {k}"
        if not any(s["status"] == "available" for s in q["simulator_suppliers"]):
            gap = q.get("simulator_gap", "")
            assert gap.startswith(TBD) or gap.startswith("n/a:"), f"quantity {name}: no available supplier and no stated gap"


def test_hall_quantities_are_not_supplied_by_superseded_or_unadmitted_models(sm):
    with open(ENSEMBLE_FILE, encoding="utf-8") as f:
        ens = json.load(f)
    for name, q in sm["quantities"].items():
        for s in q["simulator_suppliers"]:
            qual = s["ref"].split(":")[1]
            if s["ref"].startswith("abep_sim.plasma_devices:") and qual.split(".")[0] in ZERO_D_HALL:
                assert s["status"] == "superseded_do_not_use", f"{name}: 0-D Hall closure offered as a supplier"
            if s["ref"].startswith("abep_sim.hall_map:") and not ens["members"]:
                assert s["status"] == "gated", f"{name}: HallMap cannot supply anything while the credible set is empty"


def test_no_calibration_nuisance_leak(sm):
    """Layer-1 calibration nuisance (P5 evidence) is never a design/control variable (CLAUDE.md next-work item 1)."""
    with open(ENSEMBLE_FILE, encoding="utf-8") as f:
        nuisance = set(json.load(f)["calibration_nuisance"])
    names = set(sm["quantities"]) | set(sm["parameters"])
    assert not nuisance & names
    for where, e in _expressions(sm):
        assert not nuisance & set(_identifiers(e)), f"calibration nuisance in {where}"


def test_scope_milestones_and_exclusions_are_declared(sm):
    ms = sm["milestone_support"]
    assert ms["operating_model_question"] == "iii" and ms["supports"] == ["A"]
    for k in ("milestone_A", "to_reach_B", "to_reach_C", "what_could_overturn"):
        assert ms[k], k
    assert sm["verification"]["protocol"] == "single-lens-v1"
    air = [b for b in sm["excluded_branches"] if b["id"] == "air_fed_cathode"]
    assert air and air[0]["status"].startswith("EXCLUDED BY DESIGN CHOICE") and "not a physics result" in air[0]["status"]
    assert air[0]["reopen_when"].startswith(TBD)
    assert "AIR_ONLY_ANODE_XE_CATHODE" in _states(sm)
    for item in sm["literature_basis"]["items"]:
        assert item["pointers"] and item["caveat"], item["claim"]


def test_documentation_covers_states_and_quantities(sm):
    with open(DOC_FILE, encoding="utf-8") as f:
        doc = f.read()
    missing_states = [s for s in _states(sm) if f"`{s}`" not in doc]
    missing_q = [q for q in sm["quantities"] if f"`{q}`" not in doc]
    assert not missing_states, f"states not documented: {missing_states}"
    assert not missing_q, f"guard quantities without a documented supplier row: {missing_q}"
