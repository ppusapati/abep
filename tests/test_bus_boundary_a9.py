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
def _led(config, p, eta=1.0, basis="p_bus_1ms_max"):
    loads, effs = full(config, p=p, eta=eta)
    return B.ledger(config, loads, effs, {"value": 1.0, "evidence_class": "assumed", "source": "unit test"},
                    power_basis=basis)


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
    assert g["transient_window_frozen"] is True
    assert g["transient_window"]["status"] == "FROZEN_A9_ENGINEERING_DEFINITION"     # A9.1 OQ-A902-01
    assert g["transient_window"]["window_s"] == 1.0e-3


@pytest.mark.parametrize("basis", [None, "step_average", "steady_state"])
def test_pass_needs_1ms_gate_basis(basis):
    """A9.1 OQ-A902-01: P_bus,1ms,max is the gate for start-up AND steady state; no step average is substituted."""
    n = len(B.installed_slots("hall_c1_reference"))
    ok = _led("hall_c1_reference", 1000.0 / n, basis=basis)
    at = _led("hall_c1_reference", 1500.0 / n, basis=basis)
    g = B.rfp_power_gate(ok, [ok])
    assert g["rows"][0]["verdict"] == "NOT_EVALUABLE" and g["rows"][0]["note"]   # steady row now needs it too
    assert g["rows"][1]["verdict"] == "NOT_EVALUABLE" and g["rows"][1]["note"]
    assert g["verdict"] == "NOT_EVALUABLE"
    assert B.rfp_power_gate(ok, [at])["verdict"] == "FAIL"      # an average at the limit bounds the 1 ms max: fails
    with pytest.raises(B.BoundaryA9Error):
        _led("hall_c1_reference", 10.0, basis="rms")


def test_unaveraged_peak_bounds_pass_but_is_not_the_gate():
    """A9.1 OQ-A902-01: an unaveraged sampled peak below the limit bounds P_bus,1ms,max (PASS); at/above the limit it is
    a protection-analysis record, not the 1.5 kW gate (NOT_EVALUABLE)."""
    n = len(B.installed_slots("hall_icp_neutralizer"))
    ok = _led("hall_icp_neutralizer", 1000.0 / n, basis="peak_sampled")
    at = _led("hall_icp_neutralizer", 1500.0 / n, basis="peak_sampled")
    assert B.rfp_power_gate(ok, [ok])["verdict"] == "PASS"
    r = B.rfp_power_gate(ok, [at])
    assert r["verdict"] == "NOT_EVALUABLE" and "protection" in r["rows"][1]["note"]


def test_p_bus_1ms_max_from_samples():
    fs = 100.0e3
    rec = [100.0] * 150 + [2000.0] * 50 + [100.0] * 300           # 0.5 ms spike of 2 kW
    r = B.p_bus_1ms_max(rec, fs, 20.0e3, True, True)
    assert r["window_samples"] == 100
    assert r["P_bus_1ms_max_W"] == pytest.approx(1050.0)          # 50 x 2000 + 50 x 100 over 100 samples
    assert r["diagnostics_only"]["unaveraged_sampled_peak_W"] == 2000.0
    assert r["diagnostics_only"]["max_mean_100ms_W"] is None      # record shorter than 100 ms
    for args in ((rec, 50.0e3, 20.0e3, True, True), (rec, fs, 10.0e3, True, True), (rec, fs, 20.0e3, False, True),
                 (rec, fs, 20.0e3, True, False), ([1.0] * 10, fs, 20.0e3, True, True),
                 (rec, 150.5e3, 20.0e3, True, True)):
        with pytest.raises(B.BoundaryA9Error):
            B.p_bus_1ms_max(*args)


def test_icp_power_allocation_check():
    """A9.1 OQ-A902-03: P_ICP,available = 1350 - P_common - P_Hall - P_other,active; no fixed split."""
    loads, effs = full("hall_icp_neutralizer", p=10.0, eta=1.0)
    loads["hall_discharge"] = L(900.0)
    loads["icp_rf_source"] = {**L(200.0), "plane": "generator_dc_input"}
    led = B.ledger("hall_icp_neutralizer", loads, effs, {"value": 1.0, "evidence_class": "assumed", "source": "t"})
    c = B.icp_power_allocation_check(led)
    # common: 2 flow + compressor + thermal + housekeeping = 5 x 10; Hall: 900 + 3 coils x 10; other: reserved 10
    assert c["P_ICP_available_W"] == pytest.approx(1350.0 - 50.0 - 930.0 - 10.0)
    assert c["P_ICP_W"] == pytest.approx(200.0 + 10.0 + 10.0) and c["verdict"] == "WITHIN_AVAILABLE"
    loads["icp_rf_source"] = {**L(400.0), "plane": "generator_dc_input"}
    led2 = B.ledger("hall_icp_neutralizer", loads, effs, {"value": 1.0, "evidence_class": "assumed", "source": "t"})
    assert B.icp_power_allocation_check(led2)["verdict"] == "EXCEEDS_AVAILABLE"
    with pytest.raises(B.BoundaryA9Error):
        B.icp_power_allocation_check(B.ledger("hall_c1_reference", *full("hall_c1_reference"), FE))


def test_g_reuse_icp_feed_slot_only_in_variant():
    """A9.1 HIQ-06 / OQ-A902-05: G-REUSE is primary; flow_control_icp_feed exists only in a G-ATM / G-XE variant."""
    assert "flow_control_icp_feed" not in B.installed_slots("hall_icp_neutralizer")
    assert "flow_control_icp_feed" in B.installed_slots("hall_icp_neutralizer", ("flow_control_icp_feed",))
    assert B.ICP_GAS_MODES["G-REUSE"]["primary"] and B.ICP_GAS_MODES["G-REUSE"]["variant_slot"] is None
    assert B.COMBINED_C1_ICP_FLIGHT_VARIANT is None                                   # A9.1 OQ-A902-04


def test_tbd_heater_booked_on_at_conservative_power():
    """A9.1 SEQ-heater: a TBD heater is ON at its conservative booked power, never OFF; only for c1_heater."""
    loads, effs = full("hall_c1_reference", p=10.0, eta=1.0)
    loads["c1_heater"] = {"P_W": "TBD", "tbd_requires": "C1 procedure", "booked_W": 120.0,
                          "evidence_class": "assumed", "source": "unit test"}
    led = B.ledger("hall_c1_reference", loads, effs, FE1)
    it = next(i for i in led["items"] if i["slot"] == "c1_heater")
    assert it["state"] == "ON_BOOKED_TBD" and it["P_W"] == 120.0 and led["booked_tbd_slots"] == ["c1_heater"]
    assert led["status"] == "COMPLETE"
    for bad in ({"P_W": "TBD", "tbd_requires": "x", "booked_W": 0.0, "evidence_class": "assumed", "source": "t"},
                {"P_W": "TBD", "tbd_requires": "x", "booked_W": 5.0}):
        loads["c1_heater"] = bad
        with pytest.raises(B.BoundaryA9Error):
            B.ledger("hall_c1_reference", loads, effs, FE1)
    loads, effs = full("hall_c1_reference", p=10.0, eta=1.0)
    loads["c1_keeper"] = {"P_W": "TBD", "tbd_requires": "x", "booked_W": 5.0, "evidence_class": "assumed",
                          "source": "t"}
    with pytest.raises(B.BoundaryA9Error):
        B.ledger("hall_c1_reference", loads, effs, FE1)


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
    assert c["common_allocation"]["P_bus_W"] == 30.0 + 30.0 + 10.0 * 3   # compressor, 2 flow (G-REUSE: no ICP feed)


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
def _seq(config, template_events, heater=None, flags=None, basis="p_bus_1ms_max"):
    steps = []
    for i, ev in enumerate(template_events):
        loads, effs = full(config, p=10.0, eta=1.0)
        if heater is not None:
            h = heater[i]
            loads["c1_heater"] = {"P_W": "TBD", "tbd_requires": "C1 heater data"} if h == "TBD" else L(h)
        st = {"step_id": f"s{i}", "event": ev, "loads": loads, "efficiencies": effs, "power_basis": basis}
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


C1_EVS = [s["event"] for s in B.SEQUENCE_TEMPLATES["hall_c1_reference"]]


@pytest.mark.parametrize("heater", [
    [0, 0, 200, "TBD", 0, 0, 0, 0],       # known -> TBD -> 0 (reviewer reproduction)
    [0, 0, 50, 50, "TBD", 0, 0, 0],       # template events, heater 50 -> TBD -> 0
    [0, 0, "TBD", 0, 0, 0, 0, 0],         # TBD preheat -> 0 at the next step (A902-26 is TBD today)
    [0, 0, "TBD", "TBD", "TBD", 0, 0, 0],
])
def test_heater_reduction_through_tbd_is_violation(heater):
    r = B.check_startup_sequence("hall_c1_reference", _seq("hall_c1_reference", C1_EVS, heater, [{}] * 8), FE1)
    assert r["sequence_status"] == "SEQUENCE_RULE_VIOLATION"
    assert any("heater" in v["rule"] for v in r["violations"])


def test_heater_tbd_with_stability_flags_satisfied_and_unclassifiable_not_evaluable():
    flags = [{}] * 6 + [{"keeper_stable": True, "discharge_stable": True}] * 2
    ok = B.check_startup_sequence("hall_c1_reference",
                                  _seq("hall_c1_reference", C1_EVS, [0, 0, "TBD", "TBD", "TBD", "TBD", 0, 0], flags),
                                  FE1)
    assert ok["sequence_status"] == "RULES_SATISFIED", (ok["violations"], ok["not_evaluable"])
    ne = B.check_startup_sequence("hall_c1_reference",
                                  _seq("hall_c1_reference", C1_EVS, [0, 0, "TBD", 40, 40, 40, 0, 0], flags), FE1)
    assert ne["sequence_status"] == "RULES_NOT_EVALUABLE" and ne["not_evaluable"]
    assert not ne["violations"]


def test_undeclared_simultaneous_peak_loads_detected_by_magnitude():
    evs = [None, "magnet_ramp", "icp_rf_ignition", "icp_collector_bias_on", "hall_discharge_ignition", None]
    steps = _seq("hall_icp_neutralizer", evs)
    steps[2] = copy.deepcopy(steps[2])
    steps[2]["loads"]["compressor"] = L(200.0)                  # compressor jumps in the RF-ignition step, no label
    steps[2]["loads"]["icp_rf_source"] = {**L(300.0), "plane": "generator_dc_input"}
    r = B.check_startup_sequence("hall_icp_neutralizer", steps, FE1)
    assert any("load rises" in v["rule"] for v in r["violations"]), r["violations"]
    steps[2]["loads"]["compressor"] = {"P_W": "TBD", "tbd_requires": "compressor ICD"}
    r2 = B.check_startup_sequence("hall_icp_neutralizer", steps, FE1)
    assert any("load rises" in v["rule"] for v in r2["not_evaluable"]) or \
        any("load rises" in v["rule"] for v in r2["violations"])


def test_record_shape_refusals_schema_parity():
    loads, effs = full("hall_icp_neutralizer")
    for bad in ({**loads, "c1_heater": {"P_W": 0}},                        # not installed but no evidence/source
                {**loads, "hall_discharge": {**L(1.0), "plane": "generator_dc_input"}},   # plane only on RF source
                {**loads, "hall_discharge": {**L(1.0), "note": "x"}},       # unexpected key
                {**loads, "hall_discharge": {"P_W": "TBD", "tbd_requires": "x", "evidence_class": "assumed"}}):
        with pytest.raises(B.BoundaryA9Error):
            B.ledger("hall_icp_neutralizer", bad, effs, FE)
    with pytest.raises(B.BoundaryA9Error):
        B.ledger("hall_icp_neutralizer", loads, {**effs, "c1_heater": 1.0}, FE)   # bare number, not a record
    with pytest.raises(B.BoundaryA9Error):
        B.ledger("hall_icp_neutralizer", loads, effs, {**FE, "path": "direct"})   # front end has no path


# ---- minimal JSON-Schema subset validator (jsonschema is not a dependency); used for module/schema parity
def _valid(inst, sch, root):
    if "$ref" in sch:
        return _valid(inst, root["$defs"][sch["$ref"].split("/")[-1]], root)
    if "oneOf" in sch:
        return sum(_valid(inst, s, root) for s in sch["oneOf"]) == 1
    if "const" in sch and inst != sch["const"]:
        return False
    if "enum" in sch and inst not in sch["enum"]:
        return False
    t = sch.get("type")
    if t == "object":
        if not isinstance(inst, dict) or any(k not in inst for k in sch.get("required", [])):
            return False
        props = sch.get("properties", {})
        if "propertyNames" in sch and not all(_valid(k, sch["propertyNames"], root) for k in inst):
            return False
        for k, v in inst.items():
            if k in props:
                if not _valid(v, props[k], root):
                    return False
            elif sch.get("additionalProperties") is False:
                return False
            elif isinstance(sch.get("additionalProperties"), dict) and not _valid(v, sch["additionalProperties"],
                                                                                   root):
                return False
        return True
    if t == "number":
        if isinstance(inst, bool) or not isinstance(inst, (int, float)):
            return False
        if "minimum" in sch and inst < sch["minimum"]:
            return False
        if "maximum" in sch and inst > sch["maximum"]:
            return False
        if "exclusiveMinimum" in sch and inst <= sch["exclusiveMinimum"]:
            return False
    if t == "string" and (not isinstance(inst, str) or len(inst) < sch.get("minLength", 0)):
        return False
    if t == "array":
        if not isinstance(inst, list):
            return False
        if sch.get("uniqueItems") and len(set(map(str, inst))) != len(inst):
            return False
        return all(_valid(x, sch["items"], root) for x in inst)
    return True


def _both_validators(doc, sch):
    ok = _valid(doc, sch, sch)
    try:
        import jsonschema  # optional
    except ImportError:
        return ok
    assert jsonschema.Draft202012Validator(sch).is_valid(doc) == ok
    return ok


RF_OK = {**L(100.0), "plane": "generator_dc_input"}
LOAD_CASES = [("hall_discharge", L(10.0)), ("hall_discharge", {"P_W": "TBD", "tbd_requires": "x"}),
              ("hall_discharge", {"P_W": 1.0}), ("hall_discharge", {**L(1.0), "plane": "generator_dc_input"}),
              ("hall_discharge", {**L(1.0), "note": "x"}), ("hall_discharge", L(-1.0)),
              ("icp_rf_source", RF_OK), ("icp_rf_source", L(100.0)), ("icp_rf_source", {**L(1.0), "plane": "forward"}),
              ("icp_rf_source", {"P_W": "TBD", "tbd_requires": "x", "plane": "generator_dc_input"}),
              ("icp_rf_source", {"P_W": "TBD", "tbd_requires": "x"})]


@pytest.mark.parametrize("slot,rec", LOAD_CASES)
def test_module_and_schema_agree_on_load_records(slot, rec):
    sch = json.load(open(OUT_SCHEMA, encoding="utf-8"))
    loads, effs = full("hall_icp_neutralizer")
    loads[slot] = rec
    doc = {"boundary_version": B.BOUNDARY_VERSION, "configuration": "hall_icp_neutralizer", "variant": [],
           "front_end": FE, "loads": loads, "efficiencies": effs, "power_basis": "peak_sampled"}
    try:
        B.ledger("hall_icp_neutralizer", loads, effs, FE, power_basis="peak_sampled")
        mod_ok = True
    except B.BoundaryA9Error:
        mod_ok = False
    assert mod_ok == _both_validators(doc, sch)


def test_module_and_schema_agree_on_not_installed_zero_record():
    sch = json.load(open(OUT_SCHEMA, encoding="utf-8"))
    loads, effs = full("hall_icp_neutralizer")
    for rec, expect in ((L(0.0), True), ({"P_W": 0}, False)):
        doc = {"boundary_version": B.BOUNDARY_VERSION, "configuration": "hall_icp_neutralizer", "variant": [],
               "front_end": FE, "loads": {**loads, "c1_heater": rec}, "efficiencies": effs}
        assert _both_validators(doc, sch) is expect
        if expect:
            B.ledger("hall_icp_neutralizer", doc["loads"], effs, FE)
        else:
            with pytest.raises(B.BoundaryA9Error):
                B.ledger("hall_icp_neutralizer", doc["loads"], effs, FE)


def test_documented_limitations(data):
    ba = data["bus_architecture"]
    assert "housekeeping_controls" in ba["no_load_losses"] and "floating-point" in ba["residual_check"]
    assert "compressor LOAD" in ba["status_taxonomy"]
    assert "pulse energy" in B.SLOTS["c1_keeper"]["load_plane"] and "not a ledger field" in \
        B.SLOTS["c1_keeper"]["load_plane"]


def test_h2_4_flags_and_h2_7_mass_lines(data):
    flags = {f["h2_4_id"]: f["disposition"] for f in data["h2_4_revision_flags"]}
    for pid in ("H24-05", "H24-06", "H24-07", "H24-08", "H24-09", "H24-10", "H24-11", "H24-19", "H24-24",
                "H24-26", "H24-35"):
        assert pid in flags, pid
    assert flags["H24-26"] == "NEEDS_REVISION" and flags["H24-19"] == "NEEDS_REVISION"
    assert flags["H24-35"] == "CONSTRAINED_BY_OWNER_ANSWER"
    a35 = next(i for i in data["items"] if i["id"] == "A902-35")["source"]
    assert "28 V" not in a35 and "100 V +/- 3 V" in a35
    h27 = [x for x in data["interface_demands"] if x["from"] == "A9-02" and x["to"] == "H2-7"]
    elec = next(x for x in h27 if x["quantity"].startswith("PPU/RF electronics"))
    assert "icp_neutralizer_kg" not in elec["value"]
    head = next(x for x in h27 if "SOURCE-HEAD" in x["quantity"])
    assert head["value"] == {"icp_neutralizer_kg": 2.0}
    a01 = next(i for i in data["items"] if i["id"] == "A902-01")
    assert a01["evidence_class"] == "requirement-as-recorded"
