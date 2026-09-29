"""Tests for A9-02 bus_power_boundary_a9_v1 (abep_sim/bus_boundary_a9.py + docs/architecture_comparison/power_boundary_a9/).

Only this lane's files are exercised; no parallel A9 lane is imported or read. All loads below are synthetic test
inputs labelled 'assumed' / source 'unit test' -- they are not engineering values.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os

import pytest

from abep_sim import bus_boundary_a9 as B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANE = os.path.join(ROOT, "docs", "architecture_comparison", "power_boundary_a9")
BUILDER = os.path.join(LANE, "build_bus_power_boundary_a9.py")
OUT_JSON = os.path.join(LANE, "bus_power_boundary_a9_v1.json")
OUT_MD = os.path.join(LANE, "BUS_POWER_BOUNDARY_A9.md")
OUT_SCHEMA = os.path.join(ROOT, "schemas", "interfaces", "bus_power_boundary_a9_v1.json")
V1 = os.path.join(ROOT, "abep_sim", "arch_boundary.py")
V1_SHA = "8dfc309a5d2c717913fd4961bc660f8bab92ed2c59356f5a78bff3ef4392eeae"
FE = {"value": 0.95, "evidence_class": "assumed", "source": "unit test"}


def _mod():
    spec = importlib.util.spec_from_file_location("build_bus_power_boundary_a9", BUILDER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def mod():
    return _mod()


@pytest.fixture(scope="module")
def data():
    with open(OUT_JSON, encoding="utf-8") as f:
        return json.load(f)


def L(p):
    return {"P_W": p, "evidence_class": "assumed", "source": "unit test"}


def E(v=0.9, path="internal_bus"):
    return {"value": v, "evidence_class": "assumed", "source": "unit test", "path": path}


def full(config, variant=(), p=10.0, eta=0.9):
    inst = B.installed_slots(config, variant)
    loads = {s: L(p) for s in inst}
    if "icp_rf_source" in loads:
        loads["icp_rf_source"]["plane"] = "generator_dc_input"
    return loads, {s: E(eta) for s in inst}


# ------------------------------------------------------------------------------------------------ v1 untouched
def test_v1_module_byte_identical_by_sha256():
    with open(V1, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == V1_SHA


def test_module_is_pure_and_not_wired():
    src = open(os.path.join(ROOT, "abep_sim", "bus_boundary_a9.py"), encoding="utf-8").read()
    for banned in ("open(", "xe_ledger"):
        assert banned not in src, banned
    imports = [ln.split()[1] for ln in src.splitlines() if ln.startswith(("import ", "from "))]
    assert set(imports) <= {"__future__", "math", "collections.abc", "numbers"}, imports
    eng = open(os.path.join(ROOT, "abep_sim", "archengine.py"), encoding="utf-8").read()
    assert "bus_boundary_a9" not in eng


# ------------------------------------------------------------------------------------------------ builder
def test_outputs_reproduce_byte_for_byte(mod):
    d = mod.build(mod.load_inputs())
    assert open(OUT_JSON, encoding="utf-8").read() == mod.dumps(d)
    assert open(OUT_MD, encoding="utf-8").read() == mod.render_md(d)
    assert open(OUT_SCHEMA, encoding="utf-8").read() == mod.dumps(mod.build_schema())


def test_decision_pins(data):
    pins = {p["key"]: p["sha256"] for p in data["decision_pins"]}
    assert pins["A9"] == "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f"
    assert pins["ANS"] == "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"
    assert pins["PACK"] == "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976"
    assert data["historical_boundary_untouched"]["sha256"] == V1_SHA


def test_no_mutable_governance_pinned(mod, data):
    for path, _sha, _role in mod.INPUTS.values():
        assert not any(b in path for b in mod.BANNED_PINS), path
    assert data["compliance"]["pins_mutable_governance"] is False


def test_changed_or_missing_pin_refuses(mod, monkeypatch):
    bad = dict(mod.INPUTS)
    path, _sha, role = bad["A9"]
    bad["A9"] = (path, "0" * 64, role)
    monkeypatch.setattr(mod, "INPUTS", bad)
    with pytest.raises(mod.A902InputError):
        mod.load_inputs()
    bad2 = dict(mod.INPUTS)
    bad2["H24"] = ("docs/does/not/exist.json", "0" * 64, "x")
    monkeypatch.setattr(mod, "INPUTS", bad2)
    with pytest.raises(mod.A902InputError):
        mod.load_inputs()


def test_owner_answers_verbatim_from_pinned_file(data):
    ans = json.load(open(os.path.join(ROOT, "docs/decisions/OD_2026_09_29_owner_answers_147.json"), encoding="utf-8"))
    by = {a["row"]: a["owner_answer_verbatim"] for a in ans["answers"]}
    rows = {a["row"] for a in data["owner_answers_applied"]}
    assert {22, 66, 69, 70, 72, 89, 91, 108, 109, 110, 111, 112, 114} <= rows
    for a in data["owner_answers_applied"]:
        assert a["owner_answer_verbatim"] == by[a["row"]]


def test_required_sections_and_item_fields(data):
    for k in ("items", "interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
              "m16_impact", "h3_inputs", "h4_inputs", "h2_4_revision_flags"):
        assert data[k], k
    for it in data["items"]:
        for f in ("id", "value", "units", "basis", "source", "evidence_class", "status", "freeze_point"):
            assert f in it, (it["id"], f)
        assert it["freeze_point"] in ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
        if it["value"] == "TBD":
            assert it["evidence_class"] == "TBD"
    targets = {x["to"] for x in data["interface_demands"]} | {x["from"] for x in data["interface_demands"]}
    assert {"A9-01", "A9-03", "A9-04", "A9-05", "H2-4", "H2-7"} <= targets
    for x in data["interface_demands"]:
        if x["from"] in ("A9-01", "A9-03", "A9-04", "A9-05"):
            assert x["status"].startswith("PENDING "), x


def test_owner_values_cited_by_row(data):
    items = {i["id"]: i for i in data["items"]}
    assert items["A902-01"]["value"] == 1500.0 and "row 108" in items["A902-01"]["source"]
    assert items["A902-04"]["value"] == 1350.0 and "row 109" in items["A902-04"]["source"]
    assert items["A902-07"]["value"] == 300.0 and items["A902-08"]["value"] == 50.0
    assert items["A902-11"]["value"] == 100.0 and "row 111" in items["A902-11"]["source"]
    assert items["A902-17"]["value"] == [0.0, 500.0] and "row 72" in items["A902-17"]["source"]
    assert items["A902-32"]["value"] == "TBD"      # no Hall discharge prediction
    assert items["A902-06"]["value"] == 150.0 and items["A902-14"]["value"] == 13.5


def test_configuration_matrix(data):
    m = {s["slot"]: s["configurations"] for s in data["slots"]}
    assert m["icp_rf_source"] == {"hall_c1_reference": "NOT_INSTALLED", "hall_icp_neutralizer": "INSTALLED"}
    assert m["c1_heater"] == {"hall_c1_reference": "INSTALLED", "hall_icp_neutralizer": "NOT_INSTALLED"}
    assert m["filter_getter"]["hall_icp_neutralizer"] == "NOT_INSTALLED"
    assert m["icp_assist_magnet"]["hall_icp_neutralizer"] == "VARIANT_ONLY"
    assert m["active_cooling"] == {"hall_c1_reference": "VARIANT_ONLY", "hall_icp_neutralizer": "VARIANT_ONLY"}
    for s in ("hall_discharge", "hall_magnet_inner", "hall_magnet_outer", "hall_magnet_trim", "compressor",
              "reserved_dc_port", "housekeeping_controls", "thermal_control"):
        assert set(m[s].values()) == {"INSTALLED"}, s


def test_schema_enums_match_module():
    s = json.load(open(OUT_SCHEMA, encoding="utf-8"))
    assert s["properties"]["boundary_version"]["const"] == "bus_power_boundary_a9_v1"
    assert s["properties"]["configuration"]["enum"] == list(B.CONFIGURATIONS)
    assert s["properties"]["loads"]["propertyNames"]["enum"] == list(B.ALL_SLOTS)


# ------------------------------------------------------------------------------------------------ ledger
@pytest.mark.parametrize("config", B.CONFIGURATIONS)
def test_complete_ledger_sums_and_closes(config):
    loads, effs = full(config)
    led = B.ledger(config, loads, effs, FE)
    n = len(B.installed_slots(config))
    assert led["status"] == "COMPLETE"
    assert math.isclose(led["P_bus_W"], n * 10.0 / 0.9 / 0.95, rel_tol=1e-12)
    assert abs(led["residual_W"]) <= 1e-9


def test_not_installed_slots_exactly_zero():
    loads, effs = full("hall_icp_neutralizer")
    led = B.ledger("hall_icp_neutralizer", loads, effs, FE)
    for it in led["items"]:
        if it["state"] == "NOT_INSTALLED":
            assert it["P_bus_W"] == 0.0 and it["P_W"] == 0.0
    assert {it["slot"] for it in led["items"] if it["state"] == "NOT_INSTALLED"} >= {"c1_heater", "c1_keeper",
                                                                                         "filter_getter"}
    loads["c1_heater"] = L(0.0)      # explicit exact zero accepted
    B.ledger("hall_icp_neutralizer", loads, effs, FE)
    loads["c1_heater"] = L(1e-9)     # ICP has no thermionic heater: any power refused
    with pytest.raises(B.BoundaryA9Error):
        B.ledger("hall_icp_neutralizer", loads, effs, FE)


def test_off_slot_exactly_zero():
    loads, effs = full("hall_c1_reference")
    loads["c1_heater"] = L(0.0)
    effs["c1_heater"] = {"value": "TBD", "tbd_requires": "x", "path": "internal_bus"}
    led = B.ledger("hall_c1_reference", loads, effs, FE)
    it = next(i for i in led["items"] if i["slot"] == "c1_heater")
    assert it["state"] == "OFF" and it["P_bus_W"] == 0.0 and led["status"] == "COMPLETE"


@pytest.mark.parametrize("drop", ["loads", "efficiencies"])
def test_missing_installed_slot_raises(drop):
    loads, effs = full("hall_c1_reference")
    (loads if drop == "loads" else effs).pop("c1_keeper")
    with pytest.raises(B.BoundaryA9Error):
        B.ledger("hall_c1_reference", loads, effs, FE)


def test_refusals():
    loads, effs = full("hall_icp_neutralizer")
    for bad in ({**loads, "bogus": L(1.0)},
                {**loads, "hall_discharge": {"P_W": 1.0}},                       # no evidence class
                {**loads, "hall_discharge": L(-1.0)},
                {**loads, "hall_discharge": L(float("nan"))},
                {**loads, "hall_discharge": L(True)},
                {**loads, "hall_discharge": {"P_W": "tbd", "tbd_requires": "x"}},
                {**loads, "hall_discharge": {"P_W": "TBD"}},                     # TBD without what it requires
                {**loads, "icp_rf_source": L(100.0)},                            # no plane
                {**loads, "icp_rf_source": {**L(100.0), "plane": "forward"}}):   # forward is not a bus quantity
        with pytest.raises(B.BoundaryA9Error):
            B.ledger("hall_icp_neutralizer", bad, effs, FE)
    for bad in ({**effs, "hall_discharge": E(0.0)}, {**effs, "hall_discharge": E(1.2)},
                {**effs, "hall_discharge": E(0.9, path="bus")}):
        with pytest.raises(B.BoundaryA9Error):
            B.ledger("hall_icp_neutralizer", loads, bad, FE)
    with pytest.raises(B.BoundaryA9Error):
        B.ledger("hall_only", loads, effs, FE)                                   # v1 architecture id refused
    with pytest.raises(B.BoundaryA9Error):
        B.ledger("hall_icp_neutralizer", loads, effs, {"value": 0.9})            # front end without evidence
    with pytest.raises(B.BoundaryA9Error):
        B.installed_slots("hall_c1_reference", ("icp_assist_magnet",))          # undeclared variant


def test_variant_slots_need_declared_variant():
    loads, effs = full("hall_icp_neutralizer", ("icp_assist_magnet", "active_cooling"))
    led = B.ledger("hall_icp_neutralizer", loads, effs, FE, variant=("icp_assist_magnet", "active_cooling"))
    assert led["status"] == "COMPLETE"
    with pytest.raises(B.BoundaryA9Error):
        B.ledger("hall_icp_neutralizer", loads, effs, FE)                       # base: assist magnet not installed


def test_compressor_tbd_is_partial_boundary_and_lower_bound():
    loads, effs = full("hall_c1_reference")
    loads["compressor"] = {"P_W": "TBD", "tbd_requires": "compressor ICD (row 22)"}
    led = B.ledger("hall_c1_reference", loads, effs, FE)
    assert led["status"] == "PARTIAL_BOUNDARY" and led["P_bus_W"] is None
    n = len(B.installed_slots("hall_c1_reference")) - 1
    assert math.isclose(led["P_bus_lower_bound_W"], n * 10.0 / 0.9 / 0.95, rel_tol=1e-12)
    loads, effs = full("hall_c1_reference")
    effs["hall_discharge"] = {"value": "TBD", "tbd_requires": "breadboard eta_d", "path": "internal_bus"}
    led = B.ledger("hall_c1_reference", loads, effs, FE)
    assert led["status"] == "INCOMPLETE_EVIDENCE"
    fe_tbd = {"value": "TBD", "tbd_requires": "front-end data"}
    assert B.ledger("hall_c1_reference", *full("hall_c1_reference"), fe_tbd)["status"] == "INCOMPLETE_EVIDENCE"


# ------------------------------------------------------------------------------------------------ gates
def _led(config, p, eta=1.0):
    loads, effs = full(config, p=p, eta=eta)
    return B.ledger(config, loads, effs, {"value": 1.0, "evidence_class": "assumed", "source": "unit test"})


def test_rfp_gate_steady_and_startup():
    n = len(B.installed_slots("hall_icp_neutralizer"))
    ok = _led("hall_icp_neutralizer", 1000.0 / n)
    at = _led("hall_icp_neutralizer", 1500.0 / n)
    g = B.rfp_power_gate(ok, [ok])
    assert g["verdict"] == "PASS" and g["evidence_basis"].startswith("includes non-measured")
    assert B.rfp_power_gate(ok, [ok, at])["verdict"] == "FAIL"      # a start-up transient at 1500 W fails (strict)
    assert B.rfp_power_gate(at, [ok])["verdict"] == "FAIL"
    with pytest.raises(B.BoundaryA9Error):
        B.rfp_power_gate(ok, [])                                    # row 108: transients are part of the gate


def test_gate_not_evaluable_vs_fail_on_lower_bound():
    loads, effs = full("hall_c1_reference", p=10.0, eta=1.0)
    loads["compressor"] = {"P_W": "TBD", "tbd_requires": "x"}
    fe = {"value": 1.0, "evidence_class": "assumed", "source": "unit test"}
    partial = B.ledger("hall_c1_reference", loads, effs, fe)
    assert B.rfp_power_gate(partial, [partial])["verdict"] == "NOT_EVALUABLE"
    loads["hall_discharge"] = L(1600.0)
    over = B.ledger("hall_c1_reference", loads, effs, fe)
    assert B.rfp_power_gate(over, [partial])["verdict"] == "FAIL"   # lower bound alone already fails


def test_allocation_checks_are_owner_allocations():
    n = len(B.installed_slots("hall_icp_neutralizer"))
    a = B.allocation_checks(_led("hall_icp_neutralizer", 1400.0 / n))
    assert a["kind"].startswith("OWNER_ALLOCATION_CHECK")
    assert a["design_allocation"]["verdict"] == "EXCEEDS_ALLOCATION"
    b = B.allocation_checks(_led("hall_icp_neutralizer", 1300.0 / n))
    assert b["design_allocation"]["verdict"] == "WITHIN_ALLOCATION"
    loads, effs = full("hall_icp_neutralizer", p=10.0, eta=1.0)
    loads["thermal_control"] = L(30.0)
    loads["housekeeping_controls"] = L(30.0)
    led = B.ledger("hall_icp_neutralizer", loads, effs, {"value": 1.0, "evidence_class": "assumed", "source": "t"})
    c = B.allocation_checks(led)
    assert c["controls_thermal_allowance"]["verdict"] == "EXCEEDS_ALLOWANCE"
    assert c["common_allocation"]["P_bus_W"] == 30.0 + 30.0 + 10.0 * 4   # compressor, 2 flow, icp feed


def test_rf_power_planes():
    r = B.rf_power_planes(300.0, 200.0, 10.0, 180.0, 1.0)
    assert r["bus_crossing_W"] == 300.0 and r["measurement_only"]["net_forward_W"] == 190.0
    assert r["derived"]["match_and_line_loss_W"] == 10.0
    assert B.rf_power_planes(300.0, 200.0, 10.0, "TBD", 0.0)["measurement_only"]["delivered_W"] is None
    for args in ((300.0, 200.0, 250.0, "TBD", 1.0), (100.0, 200.0, 0.0, "TBD", 1.0), (300.0, 200.0, 10.0, 195.0, 1.0),
                 (300.0, 200.0, 10.0, "TBD", -1.0)):
        with pytest.raises(B.BoundaryA9Error):
            B.rf_power_planes(*args)


# ------------------------------------------------------------------------------------------------ sequencing
def _seq(config, template_events, heater=None, flags=None):
    steps = []
    for i, ev in enumerate(template_events):
        loads, effs = full(config, p=10.0, eta=1.0)
        if heater is not None:
            loads["c1_heater"] = L(heater[i])
        st = {"step_id": f"s{i}", "event": ev, "loads": loads, "efficiencies": effs}
        if flags is not None:
            st["flags"] = flags[i]
        if i == len(template_events) - 1:
            st["phase"] = "steady"
        steps.append(st)
    return steps


FE1 = {"value": 1.0, "evidence_class": "assumed", "source": "unit test"}


@pytest.mark.parametrize("config", B.CONFIGURATIONS)
def test_templates_satisfy_rules(config):
    evs = [s["event"] for s in B.SEQUENCE_TEMPLATES[config]]
    heater = None
    flags = None
    if config == "hall_c1_reference":
        heater = [0, 0, 50, 50, 50, 50, 0, 0]
        flags = [{}] * 6 + [{"keeper_stable": True, "discharge_stable": True}] * 2
    r = B.check_startup_sequence(config, _seq(config, evs, heater, flags), FE1)
    assert r["sequence_status"] == "RULES_SATISFIED", r["violations"]
    assert r["transient_gate"]["verdict"] == "PASS"


def test_heater_reduction_before_stable_is_violation():
    evs = [s["event"] for s in B.SEQUENCE_TEMPLATES["hall_c1_reference"]]
    heater = [0, 0, 50, 50, 0, 0, 0, 0]
    r = B.check_startup_sequence("hall_c1_reference", _seq("hall_c1_reference", evs, heater, [{}] * 8), FE1)
    assert r["sequence_status"] == "SEQUENCE_RULE_VIOLATION"
    assert any("heater" in v["rule"] for v in r["violations"])


def test_simultaneous_peaks_and_order_violations():
    evs = [None, ["compressor_spinup", "icp_rf_ignition"], "magnet_ramp", "hall_discharge_ignition",
           "icp_collector_bias_on", None]
    r = B.check_startup_sequence("hall_icp_neutralizer", _seq("hall_icp_neutralizer", evs), FE1)
    rules = [v["rule"] for v in r["violations"]]
    assert any("one peak" in x for x in rules)
    assert "icp_rf_ignition before icp_collector_bias_on" not in rules
    evs2 = [None, "magnet_ramp", "hall_discharge_ignition", "icp_rf_ignition", None]
    r2 = B.check_startup_sequence("hall_icp_neutralizer", _seq("hall_icp_neutralizer", evs2), FE1)
    assert any(v["rule"] == "icp_rf_ignition before hall_discharge_ignition" for v in r2["violations"])


def test_sequence_refusals_and_transient_gate():
    with pytest.raises(B.BoundaryA9Error):   # ICP has no heater: a heater event is refused
        B.check_startup_sequence("hall_icp_neutralizer",
                                 _seq("hall_icp_neutralizer", [None, "c1_heater_preheat", None]), FE1)
    steps = _seq("hall_icp_neutralizer", [None, "icp_rf_ignition", None])
    del steps[-1]["phase"]
    with pytest.raises(B.BoundaryA9Error):
        B.check_startup_sequence("hall_icp_neutralizer", steps, FE1)
    steps = _seq("hall_icp_neutralizer", [None, "icp_rf_ignition", None])
    steps[1] = copy.deepcopy(steps[1])
    steps[1]["loads"]["icp_rf_source"] = {**L(1600.0), "plane": "generator_dc_input"}
    r = B.check_startup_sequence("hall_icp_neutralizer", steps, FE1)
    assert r["transient_gate"]["verdict"] == "FAIL"             # transient above 1.5 kW fails even if steady passes
    assert r["transient_gate"]["rows"][0]["verdict"] == "PASS"
