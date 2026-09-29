"""THL lane: thermal / life accounting framework (abep_sim/thermal_life.py).

Checks (i) equations against hand calculations, (ii) every refusal path (missing input, unit, source, evidence, TBD
limit, extrapolation, conservation), (iii) every limit in schemas/thermal_life/limits_v1.json is sourced.

Numbers in this file are TEST FIXTURES for hand calculations. They are not design values, measurements or limits and
must never be copied into inputs. The only synthetic limit records (SYNTH_*) live in a deep copy of the limits dict,
are labelled synthetic, and exist only to exercise code paths whose real limit is TBD.
"""
import copy
import json
import math
import os

import pytest

from abep_sim import thermal_life as tl
from abep_sim.constants import E_CHARGE, K_B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T0 = 273.15


@pytest.fixture(scope="module")
def limits():
    return tl.load_limits()


@pytest.fixture(scope="module")
def contract():
    return tl.load_inputs_contract()


def num(v, unit, level=7, qtype="assumed", src="test fixture (hand calculation)"):
    return {"value": v, "unit": unit, "source": src, "evidence_level": level, "quantity_type": qtype,
            "uncertainty": "test fixture: unquantified", "applicability_domain": "test fixture only",
            "validation_status": "test fixture, not validated"}


def ident(v, src="test fixture"):
    return {"value": v, "unit": "id", "source": src}


def cond(G, Ts_K):
    return {"kind": "conductance", "G_W_per_K": num(G, "W/K"), "T_sink_K": num(Ts_K, "K")}


def mission(h=15000.0):
    return {"required_firing_h": num(h, "h", level=7, src="RFP DTDF/06/13516 (> 15,000 h firing)")}


def magnet_inputs(I=2.0, R=1.0, G=1.0, cls=155.0, policy="none", model="copper_iacs_linear", alloc=100.0, hs=10.0):
    return {"coil_current_A": num(I, "A"), "coil_resistance_ref_ohm": num(R, "ohm"),
            "coil_resistance_ref_T_C": num(20.0, "degC"), "copper_model": ident(model),
            "external_heat_W": num(0.0, "W"), "bus_power_allocation_W": num(alloc, "W"),
            "insulation_class_C": num(cls, "degC"), "derating_policy": ident(policy),
            "hot_spot_allowance_K": num(hs, "K"), "rejection_paths": [cond(G, 20.0 + T0)]}


ADMITTED_FIXTURE_ID = "adm-fixture-01"      # synthetic; NO real admitted member exists (credible set empty)


@pytest.fixture
def admitted_ensemble(monkeypatch):
    """Monkeypatched transport ensemble with one SYNTHETIC admitted member, to exercise the admitted-member path only.
    The real ensemble (hallthruster_bridge/ensemble/transport_ensemble_v0.json) has no members."""
    from abep_sim import hall_ensemble
    fake = {"members": [{"ensemble_member_id": ADMITTED_FIXTURE_ID}],
            "screening_candidates": [{"ensemble_member_id": "sgb-screen-01"}]}
    monkeypatch.setattr(hall_ensemble, "load_ensemble", lambda *a, **k: fake)
    return fake


def hallmap_prov(mid=ADMITTED_FIXTURE_ID, wlt=True, commit=None):
    return {"kind": "admitted_hallmap", "ensemble_member_id": mid, "trustworthy": True, "wall_life_trustworthy": wlt,
            "hallthruster_commit": commit or tl._pinned_hall_commit(), "map_meta_sha256": "0" * 64}


def map_meta(mid=ADMITTED_FIXTURE_ID, commit=None, iwl=True):
    """Synthetic HallMap meta subset (test fixture; no real admitted map exists)."""
    return {"schema": "hall_map_schema_v1", "ensemble_member_id": mid,
            "hallthruster_commit": commit or tl._pinned_hall_commit(), "ion_wall_losses": iwl}


STMTS = {"uncertainty": "test fixture: unquantified", "applicability_domain": "test fixture only",
         "validation_status": "test fixture, not validated"}


HW_EVIDENCE = {k: "test fixture (synthetic, not a measurement)" for k in tl.HARDWARE_EVIDENCE_FIELDS}


def wall_rec(v, unit, prov, qtype=None):
    q = qtype or ("measured" if prov and prov.get("kind") == "measured_hardware" else "model-derived")
    r = num(v, unit, level=6, qtype=q)
    if prov is not None:
        r["wall_flux_provenance"] = copy.deepcopy(prov)
    return r


def discharge_inputs(Pd=1000.0, prov="default"):
    prov = hallmap_prov() if prov == "default" else prov
    return {"discharge_power_W": num(Pd, "W"), "discharge_current_A": num(5.0, "A"),
            "wall_ion_flux_m2s": wall_rec(1e21, "m^-2 s^-1", prov), "wall_ion_energy_eV": wall_rec(50.0, "eV", prov),
            "wall_area_m2": num(0.01, "m^2"), "wall_electron_temperature_eV": num(20.0, "eV"),
            "wall_see_yield": num(0.5, "-"), "anode_electron_temperature_eV": num(5.0, "eV"),
            "additional_wall_heat_W": num(0.0, "W"), "wall_material_record": ident("bn_hebosint_pl100"),
            "wall_environment": ident("inert_or_vacuum"), "hot_spot_allowance_K": num(0.0, "K"),
            "rejection_paths": [cond(1.0, 300.0)], "allowable_erosion_depth_m": num(0.01, "m"),
            "peak_to_average_flux_ratio": num(2.0, "-"), "volumetric_sputter_yield_m3_per_ion": num(1e-30, "m^3")}


def ecr_magnet_inputs(P=100.0, f=0.1, grade="pm_sm2co17_recoma35e", Hk_T=200.0):
    return {"magnet_grade_record": ident(grade), "ecr_rf_power_W": num(P, "W"),
            "heat_fraction_to_magnets": num(f, "-"), "bus_power_allocation_W": num(0.0, "W"),
            "min_Br_fraction_required": num(0.9, "-"), "demag_field_max_A_per_m": num(3e5, "A/m"),
            "knee_field_A_per_m": num(6e5, "A/m"), "knee_field_at_T_C": num(Hk_T, "degC"),
            "hot_spot_allowance_K": num(0.0, "K"), "rejection_paths": [cond(1.0, 20.0 + T0)]}


def source_inputs(limit_rid="rf_source_structure_limit", P=200.0, fr=(0.1, 0.05, 0.05)):
    return {"rf_power_W": num(P, "W"), "heat_fraction_antenna_copper": num(fr[0], "-"),
            "heat_fraction_coupler_dielectric": num(fr[1], "-"), "heat_fraction_plasma_to_structure": num(fr[2], "-"),
            "structure_limit_record": ident(limit_rid), "hot_spot_allowance_K": num(0.0, "K"),
            "rejection_paths": [cond(1.0, 20.0 + T0)]}


def cathode_inputs():
    return {"keeper_power_W": num(10.0, "W"), "keeper_heat_fraction_to_cathode": num(0.5, "-"),
            "heater_power_W": num(50.0, "W"), "heater_steady_state_duty": num(0.0, "-"),
            "emitter_plasma_heating_W": num(20.0, "W"), "emission_current_A": num(5.0, "A"),
            "emitting_area_m2": num(5e-5, "m^2"), "insert_mass_kg": num(1e-3, "kg"),
            "emitter_pO2_Torr": num(1e-6, "Torr"), "heater_qualified_cycles": num(1000.0, "-"),
            "required_heater_cycles": num(100.0, "-"), "assembly_limit_record": ident("cathode_assembly_temperature_limit"),
            "hot_spot_allowance_K": num(0.0, "K"), "rejection_paths": [cond(1.0, 20.0 + T0)]}


def synthetic_limits(limits):
    """Deep copy with SYNTHETIC values for the TBD records, only to reach code paths. Never data."""
    L = copy.deepcopy(limits)
    L["sources"]["SYNTH_test_only"] = {"citation": "SYNTHETIC test fixture, not a source", "url": "none",
                                       "access": "test only", "accessed_on": "n/a"}

    def rec(kind, values):
        return {"status": "sourced", "kind": kind, "source_id": "SYNTH_test_only", "locator": "test",
                "evidence_level": 7, "quantity_type": "assumed", "values": values, "transformation_chain": "none",
                "uncertainty": "synthetic", "applicability_domain": "tests only", "validation_status": "synthetic"}
    for rid in ("rf_source_structure_limit", "ecr_source_structure_limit", "cathode_assembly_temperature_limit"):
        L["records"][rid] = rec("component_temperature_limit",
                                {"T_max_C": {"value": 200.0, "unit": "degC", "as_published": "SYNTHETIC"}})
    L["records"]["lab6_evaporation_rate"] = rec("emitter_evaporation_rate", {
        "T_K": {"value": [1500.0, 2500.0], "unit": "K", "as_published": "SYNTHETIC"},
        "rate_kg_m2s": {"value": [1e-12, 1e-8], "unit": "kg m^-2 s^-1", "as_published": "SYNTHETIC"}})
    return L


# ------------------------------------------------------------------------------------------------ every limit sourced
def test_every_limit_record_is_sourced_or_explicit_tbd(limits):
    assert limits["schema"] == "thermal_life_limits_v1"
    n_sourced = 0
    for rid, r in limits["records"].items():
        if r["status"] == "TBD":
            assert r["requires"].strip(), rid
            continue
        n_sourced += 1
        s = limits["sources"][r["source_id"]]
        assert s["url"] and s["accessed_on"] and s["citation"] and s["access"], rid
        assert 1 <= r["evidence_level"] <= 7 and r["quantity_type"] in tl.QUANTITY_TYPES, rid
        for k in ("locator", "transformation_chain", "uncertainty", "applicability_domain", "validation_status"):
            assert r[k].strip(), (rid, k)
        for vk, v in r["values"].items():
            assert v["as_published"].strip(), (rid, vk)
            assert v["value"] is not None or v["TBD"].strip(), (rid, vk)
    assert n_sourced >= 20
    for name, rel in limits["relations"].items():
        assert rel["source_id"] in limits["sources"] and rel["locator"] and rel["form"], name
    # external sources are URLs; the only repository source is the HallMap schema
    for sid, s in limits["sources"].items():
        assert s["url"].startswith("https://") or s["url"] == "hallthruster_bridge/hall_map_schema_v1.json", sid


def test_validate_limits_rejects_unsourced_records(limits):
    L = copy.deepcopy(limits)
    del L["records"]["copper_iacs_linear"]["locator"]
    with pytest.raises(ValueError, match="lacks 'locator'"):
        tl.validate_limits(L)
    L = copy.deepcopy(limits)
    L["records"]["bn_combat_m26"]["requires"] = ""
    with pytest.raises(ValueError, match="must say what it requires"):
        tl.validate_limits(L)
    L = copy.deepcopy(limits)
    L["records"]["copper_iacs_linear"]["values"]["alpha_20C"]["value"] = None
    with pytest.raises(ValueError, match="null without a TBD"):
        tl.validate_limits(L)
    L = copy.deepcopy(limits)
    L["records"]["copper_iacs_linear"]["source_id"] = "nowhere"
    with pytest.raises(ValueError, match="unknown source_id"):
        tl.validate_limits(L)


def test_tbd_limits_are_refused(limits):
    with pytest.raises(ValueError, match="TBD"):
        tl.limit_record(limits, "bn_combat_m26")
    with pytest.raises(ValueError, match="TBD"):
        tl.limit_value(limits, "pm_ndfeb_n42sh_arnold", "T_max_use_C")
    with pytest.raises(ValueError, match="TBD"):
        tl.lab6_evaporation_rate(1800.0, limits)
    with pytest.raises(ValueError, match="not in the limits file"):
        tl.limit_record(limits, "no_such_record")
    with pytest.raises(ValueError, match="kind"):
        tl.limit_record(limits, "copper_iacs_linear", "permanent_magnet_grade")


# ------------------------------------------------------------------------------------------------ contracts / naming
def test_contract_names_coordinate_with_bus_power_boundary(contract):
    assert tl.BUS_POWER_COMPONENTS == ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater",
                                       "rf_source", "ecr_source", "ecr_magnet")
    mapped = [b for c in contract["components"].values() for b in c["bus_power_components"]]
    assert sorted(mapped) == sorted(tl.BUS_POWER_COMPONENTS)          # each bus component feeds exactly one node
    for c in contract["components"].values():
        for k, s in c["inputs"].items():
            assert s["from"].strip(), k
            if s["kind"] == "number":
                assert s["unit"], k


def test_hallmap_field_names_come_from_the_schema():
    s = tl.load_hall_map_schema()
    with open(os.path.join(ROOT, "hallthruster_bridge", "hall_map_schema_v1.json")) as fh:
        raw = json.load(fh)
    for f in tl.HALLMAP_FIELDS_USED:
        assert f in raw["fields"] and s["fields"][f]["unit"] == raw["fields"][f]["unit"]
    assert "wall_life_trustworthy" in raw["fields"]


def test_not_wired_into_archengine():
    with open(os.path.join(ROOT, "abep_sim", "archengine.py")) as fh:
        assert "thermal_life" not in fh.read()


# ------------------------------------------------------------------------------------------------ hand calculations
def test_copper_linear_and_roeser(limits):
    a = 0.00393
    assert tl.copper_resistance_ratio(120.0, 20.0, "copper_iacs_linear", limits) == pytest.approx(1 + a * 100)
    assert tl.copper_resistance_ratio(70.0, 45.0, "copper_iacs_linear", limits) == pytest.approx(
        (1 + a * 50) / (1 + a * 25))
    # Roeser ratio: 150 C lies halfway between 100 C (1.431) and 200 C (1.862)
    assert tl.copper_resistance_ratio(150.0, 0.0, "copper_roeser_ratio", limits) == pytest.approx(0.5 * (1.431 + 1.862))
    assert tl.coil_resistance_from_geometry(100.0, 1e-6, limits) == pytest.approx(1.7241e-8 * 100 / 1e-6)
    with pytest.raises(ValueError, match="no extrapolation"):
        tl.copper_resistance_ratio(250.0, 20.0, "copper_iacs_linear", limits)
    with pytest.raises(ValueError, match="no extrapolation"):
        tl.copper_resistance_ratio(-10.0, 20.0, "copper_iacs_linear", limits)


def test_mil_prf_27_rise_formula():
    # (R - r)/r (t + 234.5) - (T - t) with R = 1.2, r = 1.0, t = 20, T = 22
    assert tl.winding_temperature_rise_mil_prf_27(1.2, 1.0, 20.0, 22.0) == pytest.approx(0.2 * 254.5 - 2.0)
    with pytest.raises(ValueError, match="more than 5 C"):
        tl.winding_temperature_rise_mil_prf_27(1.2, 1.0, 20.0, 30.0)


def test_insulation_allowable(limits):
    assert tl.insulation_allowable_C(180, "none", limits)["allowable_C"] == 180
    assert tl.insulation_allowable_C(180, "none", limits)["life_basis_status"] == "TBD"
    d = tl.insulation_allowable_C(180, "eee_inst_002_custom_0p75", limits)
    assert d["allowable_C"] == pytest.approx(135.0) and d["life_basis_status"] == "inferred"
    d = tl.insulation_allowable_C(180, "eee_inst_002_class_c_minus_20", limits)
    # MIL class C row applied to an IEC class of a custom coil is an analogy: life basis 'inferred', never 'stated'
    assert d["allowable_C"] == 160.0 and d["life_basis_h"] == 50000.0 and d["life_basis_status"] == "inferred"
    with pytest.raises(ValueError, match="not an IEC 60085 thermal class"):
        tl.insulation_allowable_C(170, "none", limits)
    assert tl.insulation_allowable_C(275, "none", limits)["allowable_C"] == 275   # +25 C steps above 250
    with pytest.raises(ValueError, match="class C"):
        tl.insulation_allowable_C(120, "eee_inst_002_class_c_minus_20", limits)
    with pytest.raises(ValueError, match="unknown derating policy"):
        tl.insulation_allowable_C(180, "house_rule", limits)


def test_radiation_and_conductance_rejection():
    paths = [{"kind": "radiation", "emissivity": 0.8, "area_m2": 0.05, "view_factor": 0.9, "T_sink_K": 3.0},
             {"kind": "conductance", "G_W_per_K": 0.2, "T_sink_K": 293.15}]
    T = 400.0
    hand = 0.8 * 5.670374419e-8 * 0.05 * 0.9 * (T ** 4 - 3.0 ** 4) + 0.2 * (T - 293.15)
    assert tl.rejected_heat_W(paths, T) == pytest.approx(hand, rel=1e-12)
    sol = tl.solve_node_temperature(hand, paths)
    assert sol["T_K"] == pytest.approx(T, rel=1e-8)


def test_hall_magnet_self_consistent_coil(limits, contract):
    # G = 1 W/K to 20 C, I = 2 A, R20 = 1 ohm: dT = 4 (1 + a dT) -> dT = 4 / (1 - 4a)
    a = 0.00393
    dT = 4.0 / (1.0 - 4.0 * a)
    r = tl.check_feasibility({"mission": mission(), "hall_magnet": magnet_inputs()}, limits, ["hall_magnet"], contract)
    c = r["components"]["hall_magnet"]
    assert c["T_node"]["T_K"] - T0 == pytest.approx(20.0 + dT, rel=1e-9)
    assert c["heat_W"]["coil_I2R_W"] == pytest.approx(4.0 * (1 + a * dT), rel=1e-9)
    chk = {k["name"]: k for k in c["checks"]}
    assert chk["winding_hot_spot_temperature"]["margin"] == pytest.approx(155.0 - (20.0 + dT + 10.0), rel=1e-9)
    assert chk["insulation_life"]["status"] == tl.NOT_DEMONSTRATED        # IEC 60085 has no life basis
    assert r["status"] == tl.NOT_DEMONSTRATED
    r = tl.check_feasibility({"mission": mission(), "hall_magnet": magnet_inputs(
        cls=180.0, policy="eee_inst_002_class_c_minus_20")}, limits, ["hall_magnet"], contract)
    chk = {k["name"]: k for k in r["components"]["hall_magnet"]["checks"]}
    assert chk["insulation_life"]["status"] == tl.NOT_DEMONSTRATED        # life basis only inferred (analogy)
    assert chk["insulation_life"]["life_basis_h"] == 50000.0
    assert chk["winding_hot_spot_temperature"]["status"] == tl.PASS
    assert r["status"] == tl.NOT_DEMONSTRATED
    # allocation below the coil power -> FAIL
    r = tl.check_feasibility({"mission": mission(), "hall_magnet": magnet_inputs(alloc=1.0)}, limits,
                             ["hall_magnet"], contract)
    assert r["status"] == tl.FAIL


def test_hall_magnet_never_extrapolates_copper(limits, contract):
    # G = 0.01 W/K, I = 5 A, R = 1 ohm: balance far above 200 C -> one-sided bound, FAIL on temperature
    r = tl.check_feasibility({"mission": mission(), "hall_magnet": magnet_inputs(I=5.0, G=0.01)}, limits,
                             ["hall_magnet"], contract)
    c = r["components"]["hall_magnet"]
    assert c["T_node"]["T_K"] is None and c["T_node"]["bound"][0] == "above"
    assert c["heat_W"]["coil_I2R_W"] is None
    chk = {k["name"]: k for k in c["checks"]}
    assert chk["winding_hot_spot_temperature"]["status"] == tl.FAIL
    assert r["status"] == tl.FAIL


def test_hall_wall_heat_hand_calc(limits, contract, admitted_ensemble):
    e = E_CHARGE
    assert tl.hall_wall_ion_heat_W(1e21, 50.0, 0.01) == pytest.approx(e * 1e21 * 50.0 * 0.01)
    assert tl.hall_wall_electron_heat_W(1e21, 20.0, 0.5, 0.01) == pytest.approx(e * 1e21 * 40.0 / 0.5 * 0.01)
    assert tl.hall_anode_heat_W(5.0, 5.0) == pytest.approx(50.0)
    r = tl.check_feasibility({"mission": mission(), "hall_discharge": discharge_inputs()}, limits,
                             ["hall_discharge"], contract)
    c = r["components"]["hall_discharge"]
    Qw = e * 1e21 * 0.01 * (50.0 + 40.0 / 0.5)
    assert c["heat_W"]["wall_total_W"] == pytest.approx(Qw)
    assert c["T_node"]["T_K"] == pytest.approx(300.0 + Qw, rel=1e-9)          # G = 1 W/K
    chk = {k["name"]: k for k in c["checks"]}
    assert chk["wall_temperature"]["margin"] == pytest.approx(2000.0 - (300.0 + Qw - T0), rel=1e-9)
    life_h = 0.01 / (1e21 * 2.0 * 1e-30) / 3600.0
    assert chk["wall_erosion_life"]["margin"] == pytest.approx(life_h - 15000.0)


def test_hall_wall_energy_gate(limits, contract, admitted_ensemble):
    with pytest.raises(ValueError, match="energy conservation"):
        tl.check_feasibility({"mission": mission(), "hall_discharge": discharge_inputs(Pd=100.0)}, limits,
                             ["hall_discharge"], contract)
    with pytest.raises(ValueError, match="0 <= gamma < 1"):
        tl.hall_wall_electron_heat_W(1e21, 20.0, 1.0, 0.01)


def test_ecr_magnet_margins(limits, contract):
    # Q = 0.1 x 100 W = 10 W into G = 1 W/K at 20 C -> 30 C
    r = tl.check_feasibility({"mission": mission(), "ecr_magnet": ecr_magnet_inputs()}, limits, ["ecr_magnet"], contract)
    c = r["components"]["ecr_magnet"]
    chk = {k["name"]: k for k in c["checks"]}
    assert chk["magnet_max_use_temperature"]["margin"] == pytest.approx(300.0 - 30.0, rel=1e-9)
    assert chk["reversible_Br_loss"]["Br_fraction"] == pytest.approx(1 - 0.035 * 10.0 / 100.0, rel=1e-9)
    assert chk["irreversible_loss_knee"]["margin"] == pytest.approx(6e5 - 3e5)
    assert c["Hcj_necessary_condition"]["Hcj_min_at_T_A_per_m"] == pytest.approx(1.71e6 * (1 - 0.25 * 10.0 / 100.0))
    assert r["status"] == tl.OVERALL_PASS
    # knee field quoted at a temperature below the magnet temperature cannot demonstrate anything
    r = tl.check_feasibility({"mission": mission(), "ecr_magnet": ecr_magnet_inputs(Hk_T=25.0)}, limits,
                             ["ecr_magnet"], contract)
    assert r["status"] == tl.NOT_DEMONSTRATED
    # outside the coefficient's measured range -> NOT_DEMONSTRATED, never extrapolated
    # SmCo5 20 MGOe (Arnold RTC): coefficients 20-120 C, T_max_use 250 C; Q = 250 W into 1 W/K -> 270 C
    r = tl.check_feasibility({"mission": mission(), "ecr_magnet": ecr_magnet_inputs(
        P=2500.0, grade="pm_smco5_20mgoe_arnold_rtc")}, limits, ["ecr_magnet"], contract)
    c = r["components"]["ecr_magnet"]
    chk = {k["name"]: k for k in c["checks"]}
    assert chk["reversible_Br_loss"]["status"] == tl.NOT_DEMONSTRATED
    assert chk["magnet_max_use_temperature"]["status"] == tl.FAIL
    assert chk["magnet_max_use_temperature"]["margin"] == pytest.approx(250.0 - 270.0, rel=1e-9)
    # Recoma 35E: knee quoted at 250 C lies outside the 20-200 C Hcj coefficient range: the knee-vs-Hcj consistency
    # check is recorded as NOT_DEMONSTRATED, never skipped silently
    r = tl.check_feasibility({"mission": mission(), "ecr_magnet": ecr_magnet_inputs(Hk_T=250.0)}, limits,
                             ["ecr_magnet"], contract)
    chk = {k["name"]: k for k in r["components"]["ecr_magnet"]["checks"]}
    assert chk["knee_field_Hcj_consistency"]["status"] == tl.NOT_DEMONSTRATED
    assert chk["irreversible_loss_knee"]["status"] == tl.PASS
    assert r["status"] == tl.NOT_DEMONSTRATED
    # MMPA NdFeB family 150** C is gated (unread footnote): refused as TBD, not used as a live limit
    with pytest.raises(ValueError, match="footnote"):
        tl.check_feasibility({"mission": mission(), "ecr_magnet": ecr_magnet_inputs(grade="pm_ndfeb_mmpa")},
                             limits, ["ecr_magnet"], contract)


def test_ecr_magnet_refusals(limits, contract):
    with pytest.raises(ValueError, match="TBD"):                             # N42SH has no max-use statement
        tl.check_feasibility({"mission": mission(), "ecr_magnet": ecr_magnet_inputs(grade="pm_ndfeb_n42sh_arnold")},
                             limits, ["ecr_magnet"], contract)
    bad = ecr_magnet_inputs()
    bad["bus_power_allocation_W"] = num(5.0, "W")
    with pytest.raises(ValueError, match="permanent magnets only|must be 0 W"):
        tl.check_feasibility({"mission": mission(), "ecr_magnet": bad}, limits, ["ecr_magnet"], contract)
    bad = ecr_magnet_inputs()
    bad["knee_field_A_per_m"] = num(5e6, "A/m")
    with pytest.raises(ValueError, match="inconsistent"):
        tl.check_feasibility({"mission": mission(), "ecr_magnet": bad}, limits, ["ecr_magnet"], contract)


def test_richardson_dushman_hand_calc(limits):
    sets = {s["id"]: s for s in tl.limit_value(limits, "lab6_richardson_goebel_table6_1", "sets")}
    T = 1800.0
    kT = K_B * T / E_CHARGE
    assert tl.richardson_current_density(T, sets["lafferty_1951"]) == pytest.approx(29e4 * T * T * math.exp(-2.66 / kT))
    phi = 2.66 + 1.23e-4 * T
    assert tl.richardson_current_density(T, sets["kohl"]) == pytest.approx(120e4 * T * T * math.exp(-phi / kT))
    # source cross-check: Kohl's D = A exp(-e alpha / k) ~ 28.8 A/cm2K2 (vs Lafferty's 29)
    assert 120.0 * math.exp(-1.23e-4 / (K_B / E_CHARGE)) == pytest.approx(28.8, abs=0.05)
    J = tl.richardson_current_density(T, sets["storms_mueller_1979"])
    assert tl.emitter_temperature_K(J, sets["storms_mueller_1979"]) == pytest.approx(T, rel=1e-9)
    env = tl.emitter_temperature_envelope(1e5, limits)
    assert set(env["per_set_K"]) == set(sets) and env["T_min_K"] <= env["T_max_K"]


def test_lab6_life_hand_calc():
    # 0.9 x 1 g / (1e-10 kg/m2s x 5e-5 m2) = 1.8e8 s = 5e4 h
    assert tl.lab6_evaporation_life_h(1e-3, 0.9, 1e-10, 5e-5) == pytest.approx(0.9e-3 / 5e-15 / 3600.0)
    with pytest.raises(ValueError):
        tl.lab6_evaporation_life_h(1e-3, 1.2, 1e-10, 5e-5)


# ------------------------------------------------------------------------------------------------ TBD-limited components
def test_rf_ecr_cathode_refuse_with_real_limits(limits, contract):
    for comp, inp in (("rf_source", source_inputs()),
                      ("ecr_source", source_inputs("ecr_source_structure_limit")),
                      ("cathode", cathode_inputs())):
        with pytest.raises(ValueError, match="TBD"):
            tl.check_feasibility({"mission": mission(), comp: inp}, limits, [comp], contract)


def test_rf_source_and_cathode_paths_with_synthetic_limits(limits, contract):
    L = synthetic_limits(limits)
    r = tl.check_feasibility({"mission": mission(), "rf_source": source_inputs()}, L, ["rf_source"], contract)
    c = r["components"]["rf_source"]
    assert c["heat_W"]["total_W"] == pytest.approx(0.2 * 200.0)
    assert c["T_node"]["T_K"] - T0 == pytest.approx(20.0 + 40.0, rel=1e-9)
    assert c["checks"][0]["margin"] == pytest.approx(200.0 - 60.0, rel=1e-9)
    with pytest.raises(ValueError, match="conservation"):
        tl.check_feasibility({"mission": mission(), "rf_source": source_inputs(fr=(0.6, 0.3, 0.2))}, L,
                             ["rf_source"], contract)
    r = tl.check_feasibility({"mission": mission(), "cathode": cathode_inputs()}, L, ["cathode"], contract)
    c = r["components"]["cathode"]
    assert c["heat_W"]["total_W"] == pytest.approx(0.5 * 10.0 + 0.0 + 20.0)
    names = {k["name"] for k in c["checks"]}
    assert names == {"assembly_temperature", "emitter_evaporation_life", "emitter_O2_poisoning_screen", "heater_cycles"}


def test_ecr_shared_power_consistency(limits, contract):
    L = synthetic_limits(limits)
    inp = {"mission": mission(), "ecr_source": source_inputs("ecr_source_structure_limit", P=100.0),
           "ecr_magnet": ecr_magnet_inputs(P=120.0)}
    with pytest.raises(ValueError, match="same power"):
        tl.check_feasibility(inp, L, ["ecr_source", "ecr_magnet"], contract)
    inp = {"mission": mission(), "ecr_source": source_inputs("ecr_source_structure_limit", P=100.0, fr=(0.3, 0.3, 0.3)),
           "ecr_magnet": ecr_magnet_inputs(P=100.0, f=0.2)}
    with pytest.raises(ValueError, match="conservation"):
        tl.check_feasibility(inp, L, ["ecr_source", "ecr_magnet"], contract)


# ------------------------------------------------------------------------------------------------ input refusals
@pytest.mark.parametrize("mutate,match", [
    (lambda d: d.pop("coil_current_A"), "missing required inputs"),
    (lambda d: d.update(coil_current_A=num(2.0, "mA")), "not the contract unit"),
    (lambda d: d.update(coil_current_A={**num(2.0, "A"), "source": " "}), "no source"),
    (lambda d: d.update(coil_current_A={**num(2.0, "A"), "evidence_level": 8}), "evidence_level"),
    (lambda d: d.update(coil_current_A={**num(2.0, "A"), "quantity_type": "guessed"}), "quantity_type"),
    (lambda d: d.update(coil_current_A=num(float("nan"), "A")), "finite"),
    (lambda d: d.update(coil_current_A=2.0), "must be a record"),
    (lambda d: d["coil_current_A"].pop("uncertainty"), "lacks 'uncertainty'"),
    (lambda d: d.update(coil_current_A={**num(2.0, "A"), "applicability_domain": ""}), "applicability_domain"),
    (lambda d: d.update(coil_current_A={**num(2.0, "A"), "validation_status": None}), "validation_status"),
    (lambda d: d.update(copper_model=ident("copper_guess")), "is not one of"),
    (lambda d: d.update(rejection_paths=[]), "at least one rejection path"),
    (lambda d: d.update(rejection_paths=[{"kind": "radiation", "emissivity": num(0.8, "-")}]), "missing"),
    (lambda d: d.update(bogus=num(1.0, "W")), "unknown inputs"),
])
def test_input_refusals(limits, contract, mutate, match):
    d = magnet_inputs()
    mutate(d)
    with pytest.raises(ValueError, match=match):
        tl.check_feasibility({"mission": mission(), "hall_magnet": d}, limits, ["hall_magnet"], contract)


def test_call_level_refusals(limits, contract):
    with pytest.raises(ValueError, match="name the components"):
        tl.check_feasibility({"mission": mission()}, limits, [], contract)
    with pytest.raises(ValueError, match="unknown thermal components"):
        tl.check_feasibility({"mission": mission()}, limits, ["radiator"], contract)
    with pytest.raises(ValueError, match="no inputs given"):
        tl.check_feasibility({"mission": mission()}, limits, ["hall_magnet"], contract)
    with pytest.raises(ValueError, match="mission inputs"):
        tl.check_feasibility({"hall_magnet": magnet_inputs()}, limits, ["hall_magnet"], contract)
    with pytest.raises(ValueError, match="not requested"):
        tl.check_feasibility({"mission": mission(), "hall_magnet": magnet_inputs(), "cathode": {}}, limits,
                             ["hall_magnet"], contract)


def test_hallmap_wall_inputs_gate(admitted_ensemble):
    pinned = tl._pinned_hall_commit()
    pt = {"trustworthy": True, "wall_life_trustworthy": True, "discharge_power_W": 900.0, "discharge_current_A": 3.0,
          "wall_ion_flux_m2s": 1e21, "wall_ion_energy_eV": 40.0, "hallthruster_commit": pinned}
    out = tl.hallmap_wall_inputs(pt, ADMITTED_FIXTURE_ID, evidence_level=6, map_meta=map_meta(), **STMTS)
    assert out["wall_ion_flux_m2s"]["unit"] == "m^-2 s^-1" and out["wall_ion_energy_eV"]["unit"] == "eV"
    assert all(v["quantity_type"] == "model-derived" and v["evidence_level"] == 6 for v in out.values())
    assert out["wall_ion_flux_m2s"]["wall_flux_provenance"]["ensemble_member_id"] == ADMITTED_FIXTURE_ID
    with pytest.raises(ValueError, match="wall_life_trustworthy"):
        tl.hallmap_wall_inputs({**pt, "wall_life_trustworthy": False}, ADMITTED_FIXTURE_ID, evidence_level=6, map_meta=map_meta(), **STMTS)
    with pytest.raises(ValueError, match="not trustworthy"):
        tl.hallmap_wall_inputs({**pt, "trustworthy": False}, ADMITTED_FIXTURE_ID, evidence_level=6, map_meta=map_meta(), **STMTS)
    with pytest.raises(ValueError, match="pinned"):
        tl.hallmap_wall_inputs({**pt, "hallthruster_commit": "bfb3019"}, ADMITTED_FIXTURE_ID, evidence_level=6, map_meta=map_meta(), **STMTS)
    with pytest.raises(ValueError, match="ensemble member"):
        tl.hallmap_wall_inputs(pt, "", evidence_level=6, map_meta=map_meta(), **STMTS)
    with pytest.raises(ValueError, match="SCREENING"):
        tl.hallmap_wall_inputs(pt, "sgb-screen-01", evidence_level=6, map_meta=map_meta(), **STMTS)
    with pytest.raises(ValueError, match="not an admitted"):
        tl.hallmap_wall_inputs(pt, "member-x", evidence_level=6, map_meta=map_meta(), **STMTS)
    with pytest.raises(ValueError, match="evidence_level"):
        tl.hallmap_wall_inputs(pt, ADMITTED_FIXTURE_ID, evidence_level=0, map_meta=map_meta(), **STMTS)
    with pytest.raises(TypeError):
        tl.hallmap_wall_inputs(pt, ADMITTED_FIXTURE_ID, map_meta=map_meta(), **STMTS)   # no default evidence level
    with pytest.raises(TypeError):
        tl.hallmap_wall_inputs(pt, ADMITTED_FIXTURE_ID, evidence_level=6, **STMTS)      # map meta is required
    # the id must be the one in the queried map's meta (the query output does not carry it)
    with pytest.raises(ValueError, match="map meta ensemble_member_id"):
        tl.hallmap_wall_inputs(pt, ADMITTED_FIXTURE_ID, evidence_level=6, map_meta=map_meta("adm-other"), **STMTS)
    with pytest.raises(ValueError, match="differs from the query commit"):
        tl.hallmap_wall_inputs(pt, ADMITTED_FIXTURE_ID, evidence_level=6, map_meta=map_meta(commit="x"), **STMTS)
    with pytest.raises(ValueError, match="ion_wall_losses"):
        tl.hallmap_wall_inputs(pt, ADMITTED_FIXTURE_ID, evidence_level=6, map_meta=map_meta(iwl=False), **STMTS)
    with pytest.raises(ValueError, match="uncertainty"):
        tl.hallmap_wall_inputs(pt, ADMITTED_FIXTURE_ID, evidence_level=6, map_meta=map_meta(),
                               **{**STMTS, "uncertainty": " "})
    assert out["wall_ion_flux_m2s"]["wall_flux_provenance"]["map_meta_sha256"] == tl._canonical_sha256(map_meta())
    assert out["wall_ion_flux_m2s"]["uncertainty"] == STMTS["uncertainty"]


def test_hallmap_wall_inputs_refuses_real_ensemble():
    """Against the REAL ensemble (credible set empty): every screening candidate and unknown id is refused."""
    from abep_sim import hall_ensemble
    e = hall_ensemble.load_ensemble()
    assert hall_ensemble.member_ids(e) == set()
    pt = {"trustworthy": True, "wall_life_trustworthy": True, "discharge_power_W": 900.0, "discharge_current_A": 3.0,
          "wall_ion_flux_m2s": 1e21, "wall_ion_energy_eV": 40.0, "hallthruster_commit": tl._pinned_hall_commit()}
    for sid in sorted(hall_ensemble.screening_ids(e)):
        with pytest.raises(ValueError, match="SCREENING"):
            tl.hallmap_wall_inputs(pt, sid, evidence_level=6, map_meta=map_meta(), **STMTS)
    with pytest.raises(ValueError, match="not an admitted"):
        tl.hallmap_wall_inputs(pt, "unknown-member", evidence_level=6, map_meta=map_meta(), **STMTS)


def _discharge(inp, limits, contract):
    return tl.check_feasibility({"mission": mission(), "hall_discharge": inp}, limits, ["hall_discharge"], contract)


def test_wall_flux_gate_in_check_feasibility_real_ensemble(limits, contract):
    """G11: the erosion/heat check itself refuses screening-candidate, unknown-id and hand-entered wall flux."""
    with pytest.raises(ValueError, match="SCREENING"):
        _discharge(discharge_inputs(prov=hallmap_prov("sgb-screen-01")), limits, contract)
    with pytest.raises(ValueError, match="not an admitted"):
        _discharge(discharge_inputs(prov=hallmap_prov("unknown-member")), limits, contract)
    with pytest.raises(ValueError, match="wall_flux_provenance"):          # hand-entered, no provenance
        _discharge(discharge_inputs(prov=None), limits, contract)
    # the admitted-member provenance of the fixture is refused too, because the real ensemble admits nobody
    with pytest.raises(ValueError, match="not an admitted"):
        _discharge(discharge_inputs(), limits, contract)


def test_wall_flux_gate_paths(limits, contract, admitted_ensemble):
    ok = _discharge(discharge_inputs(), limits, contract)
    assert ok["components"]["hall_discharge"]["wall_flux_provenance"]["ensemble_member_id"] == ADMITTED_FIXTURE_ID
    hw = {"kind": "measured_hardware", "evidence_record": HW_EVIDENCE}
    r = _discharge(discharge_inputs(prov=hw), limits, contract)
    assert r["components"]["hall_discharge"]["wall_flux_provenance"]["kind"] == "measured_hardware"
    bad = [
        (discharge_inputs(prov=None), "wall_flux_provenance"),
        (discharge_inputs(prov=hallmap_prov("sgb-screen-01")), "SCREENING"),
        (discharge_inputs(prov=hallmap_prov("member-x")), "not an admitted"),
        (discharge_inputs(prov=hallmap_prov(wlt=False)), "wall_life_trustworthy"),
        (discharge_inputs(prov=hallmap_prov(commit="bfb3019")), "pinned"),
        (discharge_inputs(prov={"kind": "hand_entered"}), "provenance kind"),
        (discharge_inputs(prov={"kind": "measured_hardware", "evidence_record": {**HW_EVIDENCE, "uncertainty": ""}}),
         "evidence record lacks"),
        (discharge_inputs(prov={"kind": "measured_hardware"}), "measured_hardware provenance"),
    ]
    for inp, msg in bad:
        with pytest.raises(ValueError, match=msg):
            _discharge(inp, limits, contract)
    inp = discharge_inputs(prov=hw)                                             # hardware data must be 'measured'
    inp["wall_ion_flux_m2s"]["quantity_type"] = "assumed"
    with pytest.raises(ValueError, match="'measured'"):
        _discharge(inp, limits, contract)
    inp = discharge_inputs()                                                    # Hall-map data must be model-derived
    inp["wall_ion_energy_eV"]["quantity_type"] = "measured"
    with pytest.raises(ValueError, match="model-derived"):
        _discharge(inp, limits, contract)
    inp = discharge_inputs(prov=hw)                                             # missing quantity_type: ValueError
    inp["wall_ion_flux_m2s"].pop("quantity_type")
    with pytest.raises(ValueError, match="'measured'"):
        _discharge(inp, limits, contract)
    inp = discharge_inputs()
    inp["wall_ion_flux_m2s"].pop("quantity_type")
    with pytest.raises(ValueError, match="model-derived"):
        _discharge(inp, limits, contract)
    with pytest.raises(ValueError, match="map_meta_sha256"):
        _discharge(discharge_inputs(prov={**hallmap_prov(), "map_meta_sha256": "abc"}), limits, contract)
    inp = discharge_inputs()                                                    # flux and energy from one source
    inp["wall_ion_energy_eV"]["wall_flux_provenance"] = {"kind": "measured_hardware", "evidence_record": HW_EVIDENCE}
    inp["wall_ion_energy_eV"]["quantity_type"] = "measured"
    with pytest.raises(ValueError, match="same Hall-map point"):
        _discharge(inp, limits, contract)
