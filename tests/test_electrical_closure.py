"""Electrical closure (lane PPUMAG): magnet power model hand checks, refusal paths, and the evidence data file.

Runs standalone: `python -m pytest -q tests/test_electrical_closure.py`. Needs no other lane's files and no network.
"""
from __future__ import annotations

import csv
import importlib.util
import inspect
import json
import math
import re
from pathlib import Path

import pytest

from abep_sim import magnet_power as mp

ROOT = Path(__file__).resolve().parents[1]
EC = ROOT / "docs" / "architecture_comparison" / "electrical_closure"
DATA = EC / "electrical_closure_data_v1.json"
EXAMPLE = EC / "worked_example_v1.json"
SCHEMA = ROOT / "schemas" / "architecture_comparison" / "electrical_closure_v1.schema.json"
CSV_RHODES = EC / "sources" / "rhodes2024_slide11_discharge_efficiency.csv"
BUILD = EC / "tools" / "build_electrical_closure_data.py"
CU = mp.ANNEALED_COPPER_IACS
MIL = 0.0254e-3
FT = 0.3048
COMPONENTS = ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control", "compressor",
              "thermal_control", "housekeeping", "rf_source", "ecr_source", "ecr_magnet")
SIX = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}


# ------------------------------------------------------------------------------------------ minimal schema check
def _validate(inst, schema, root, path="$"):
    """Subset of JSON Schema 2020-12 used by electrical_closure_v1.schema.json; returns a list of error strings."""
    errs = []
    if "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/$defs/")
        errs += _validate(inst, root["$defs"][ref[len("#/$defs/"):]], root, path)
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        ok = False
        for ty in types:
            ok |= {"object": isinstance(inst, dict), "array": isinstance(inst, list), "string": isinstance(inst, str),
                   "null": inst is None, "boolean": isinstance(inst, bool),
                   "integer": isinstance(inst, int) and not isinstance(inst, bool),
                   "number": isinstance(inst, (int, float)) and not isinstance(inst, bool)}[ty]
        if not ok:
            return errs + [f"{path}: type {type(inst).__name__} not in {types}"]
    if "const" in schema and inst != schema["const"]:
        errs.append(f"{path}: {inst!r} != const {schema['const']!r}")
    if "enum" in schema and inst not in schema["enum"]:
        errs.append(f"{path}: {inst!r} not in enum")
    if isinstance(inst, str):
        if len(inst) < schema.get("minLength", 0):
            errs.append(f"{path}: shorter than minLength")
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            errs.append(f"{path}: {inst!r} !~ {schema['pattern']}")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in schema and inst < schema["minimum"]:
            errs.append(f"{path}: < minimum")
        if "maximum" in schema and inst > schema["maximum"]:
            errs.append(f"{path}: > maximum")
        if "exclusiveMinimum" in schema and not inst > schema["exclusiveMinimum"]:
            errs.append(f"{path}: <= exclusiveMinimum")
    if isinstance(inst, list):
        if len(inst) < schema.get("minItems", 0):
            errs.append(f"{path}: fewer than minItems")
        if "items" in schema:
            for i, v in enumerate(inst):
                errs += _validate(v, schema["items"], root, f"{path}[{i}]")
    if isinstance(inst, dict):
        for k in schema.get("required", []):
            if k not in inst:
                errs.append(f"{path}: missing required {k!r}")
        if len(inst) < schema.get("minProperties", 0):
            errs.append(f"{path}: fewer than minProperties")
        props = schema.get("properties", {})
        for k, v in inst.items():
            if "propertyNames" in schema:
                errs += _validate(k, schema["propertyNames"], root, f"{path}.<name {k}>")
            if k in props:
                errs += _validate(v, props[k], root, f"{path}.{k}")
            elif "additionalProperties" in schema:
                ap = schema["additionalProperties"]
                if ap is False:
                    errs.append(f"{path}: additional property {k!r}")
                elif isinstance(ap, dict):
                    errs += _validate(v, ap, root, f"{path}.{k}")
    for sub in schema.get("allOf", []):
        errs += _validate(inst, sub, root, path)
    if "anyOf" in schema and all(_validate(inst, s, root, path) for s in schema["anyOf"]):
        errs.append(f"{path}: matches no anyOf branch")
    if "if" in schema:
        branch = "then" if not _validate(inst, schema["if"], root, path) else "else"
        if branch in schema:
            errs += _validate(inst, schema[branch], root, path)
    return errs


@pytest.fixture(scope="module")
def data():
    return json.loads(DATA.read_text())


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA.read_text())


# ------------------------------------------------------------------------------------------------ AWG, copper [E3/E4]
def test_awg_definition_points():
    assert mp.awg_diameter_m(36) == pytest.approx(0.0050 * 0.0254, rel=1e-12)
    assert mp.awg_diameter_m(-3) == pytest.approx(0.4600 * 0.0254, rel=1e-12)       # No. 0000
    # NBS HB100 Table 5/6 tabulated diameter for No. 24 is 20.1 mil (rounded to 0.1 mil)
    assert abs(mp.awg_diameter_m(24) / MIL - 20.1) < 0.05
    assert abs(mp.awg_diameter_m(10) / MIL - 101.9) < 0.05                              # Table 5 No. 10: 101.9 mil


@pytest.mark.parametrize("gauge,diam_mil,table", [
    # NBS Handbook 100 Table 6 (p. 16): ohms per 1,000 ft at 0, 20, 25, 50, 75, 100, 200 C
    (24, 20.1, (23.7, 25.7, 26.2, 28.7, 31.2, 33.7, 43.8)),
    (-3, 460.0, (0.04516, 0.04901, 0.04998, 0.05479, 0.05961, 0.06442, 0.08369)),
])
def test_resistance_vs_nbs_table6(gauge, diam_mil, table):
    A = math.pi * (diam_mil * MIL) ** 2 / 4.0
    for T, R_tab in zip((0.0, 20.0, 25.0, 50.0, 75.0, 100.0, 200.0), table):
        R = mp.wire_resistance_ohm(1000 * FT, A, CU, T)
        # table values are rounded (3 significant figures above 1 ohm, 4 below): agree within one unit of the last digit
        ulp = 10 ** (math.floor(math.log10(R_tab)) - (2 if R_tab > 1 else 3))
        assert abs(R - R_tab) <= ulp, (T, R, R_tab)


def test_temperature_dependence_is_the_iec_coefficient():
    assert mp.resistance_factor(CU, 20.0) == 1.0
    assert mp.resistance_factor(CU, 100.0) == pytest.approx(1.0 + 0.00393 * 80.0, rel=1e-12)
    P20 = mp.coil_power_continuous_W(100.0, 1e-4, 0.5, 0.1, CU, 20.0)
    P100 = mp.coil_power_continuous_W(100.0, 1e-4, 0.5, 0.1, CU, 100.0)
    P200 = mp.coil_power_continuous_W(100.0, 1e-4, 0.5, 0.1, CU, 200.0)
    assert P100 / P20 == pytest.approx(1.3144, rel=1e-12)
    assert P200 / P20 == pytest.approx(1.7074, rel=1e-12)
    # linear in T: equal steps give equal increments
    assert P200 - P100 == pytest.approx((P100 - P20) * 100.0 / 80.0, rel=1e-12)


@pytest.mark.parametrize("T", [-0.1, 200.1, 250.0, -40.0])
def test_copper_outside_stated_linear_domain_is_refused(T):
    with pytest.raises(ValueError, match="validity domain"):
        mp.resistance_factor(CU, T)
    with pytest.raises(ValueError, match="validity domain"):
        mp.coil_power_continuous_W(100.0, 1e-4, 0.5, 0.1, CU, T)


# --------------------------------------------------------------------------------------------- magnetic circuit [E1]
def test_ampere_turns_ideal_core_hand_calc():
    out = mp.ampere_turns(0.015, 0.02, 2e-3, (), 1.0)
    assert out["NI_A"] == pytest.approx(0.015 * 0.02 / 1.25663706127e-6, rel=1e-12)
    assert out["NI_A"] == pytest.approx(238.73, abs=0.01)
    assert out["mmf_core_A"] == 0.0


def test_ampere_turns_with_core_and_leakage_hand_calc():
    seg = mp.CoreSegment("yoke", 0.2, 1e-3, 1000.0, 1.0)
    out = mp.ampere_turns(0.015, 0.02, 2e-3, (seg,), 1.5)
    B_core = 1.5 * 0.015 * 2e-3 / 1e-3
    F_core = B_core * 0.2 / (mp.MU0_N_PER_A2 * 1000.0)
    assert out["segments"][0]["B_T"] == pytest.approx(0.045, rel=1e-12)
    assert out["mmf_core_A"] == pytest.approx(F_core, rel=1e-12)
    assert out["NI_A"] == pytest.approx(0.015 * 0.02 / mp.MU0_N_PER_A2 + F_core, rel=1e-12)


def test_saturated_core_is_refused():
    seg = mp.CoreSegment("thin yoke", 0.2, 1e-5, 1000.0, 1.0)
    with pytest.raises(ValueError, match="exceeds its declared limit"):
        mp.ampere_turns(0.015, 0.02, 2e-3, (seg,), 1.5)


# ---------------------------------------------------------------------------------------------------- coil [E5]
def test_coil_power_hand_calc():
    # P = NI^2 rho l_mt / (k A_w) = 100^2 * 1.7241e-8 * 0.1 / (0.5 * 1e-4)
    assert mp.coil_power_continuous_W(100.0, 1e-4, 0.5, 0.1, CU, 20.0) == pytest.approx(0.34482, rel=1e-12)


def test_integer_coil_equals_continuous_limit_when_turns_are_exact():
    d = mp.awg_diameter_m(24)
    A_cu = math.pi * d * d / 4.0
    A_w = 100 * A_cu / 0.5                                    # exactly 100 turns at fill 0.5
    coil = mp.coil_design(250.0, A_w, 0.5, 0.15, d, CU, 60.0)
    assert coil["N_turns"] == 100
    assert coil["I_A"] == pytest.approx(2.5, rel=1e-12)
    assert coil["P_W"] == pytest.approx(mp.coil_power_continuous_W(250.0, A_w, 0.5, 0.15, CU, 60.0), rel=1e-10)
    assert coil["R_ohm"] == pytest.approx(1.7241e-8 * 100 * 0.15 / A_cu * (1 + 0.00393 * 40.0), rel=1e-12)
    assert coil["copper_mass_kg"] == pytest.approx(8890.0 * 100 * 0.15 * A_cu, rel=1e-12)
    assert coil["V_V"] == pytest.approx(coil["I_A"] * coil["R_ohm"], rel=1e-12)


def test_power_is_gauge_independent_in_the_continuous_limit():
    """P depends on NI, window, fill, turn length and T only; a thinner wire trades current for turns."""
    ps = []
    A_w = 400 * math.pi * mp.awg_diameter_m(22) ** 2 / 4.0 / 0.45      # one window for every gauge
    for g in (18, 22, 26, 30):
        d = mp.awg_diameter_m(g)
        ps.append(mp.coil_power_continuous_W(300.0, A_w, 0.45, 0.2, CU, 80.0))
        c = mp.coil_design(300.0, A_w, 0.45, 0.2, d, CU, 80.0)
        assert c["P_W"] == pytest.approx(ps[-1], rel=0.02)    # integer-turn rounding only
    assert max(ps) == min(ps)


def test_electromagnet_power_scales_with_B_squared():
    seg = (mp.CoreSegment("yoke", 0.2, 1e-3, 1000.0, 1.5),)
    args = dict(gap_length_m=0.02, gap_area_m2=2e-3, core_segments=seg, leakage_factor=1.5, window_area_m2=1e-4,
                fill_factor=0.5, mean_turn_length_m=0.2, wire_diameter_m=mp.awg_diameter_m(24), material=CU, T_C=20.0)
    a = mp.electromagnet(B_gap_T=0.015, **args)
    b = mp.electromagnet(B_gap_T=0.030, **args)
    assert b["P_continuous_limit_W"] / a["P_continuous_limit_W"] == pytest.approx(4.0, rel=1e-12)
    assert a["evidence_class"] == "model-derived" and a["kind"] == "electromagnet"


def test_wire_that_does_not_fit_is_refused():
    with pytest.raises(ValueError, match="does not fit"):
        mp.coil_design(100.0, 1e-6, 0.3, 0.1, mp.awg_diameter_m(10), CU, 20.0)


# ------------------------------------------------------------------------------------------- permanent magnet [E2]
def test_permanent_magnet_hand_calc_and_kirtley_limit():
    out = mp.permanent_magnet(0.1, 0.01, 1e-3, (), 1.0, 1e-3, 1.0, 1.0, 2e6, 8400.0)
    assert out["P_load_W"] == 0.0
    assert out["B_m_T"] == pytest.approx(0.1, rel=1e-12)
    assert out["magnet_length_m"] == pytest.approx(0.01 * 0.1 / 0.9, rel=1e-12)       # l_m = g B_g / (B_r - B_m)
    # Kirtley 6.061 Sec. 4.3: B_m = B0 P_u / (1 + P_u), P_u = (A_g/g) / (A_m/l_m)
    Pu = (1e-3 / 0.01) / (1e-3 / out["magnet_length_m"])
    assert out["B_m_T"] == pytest.approx(1.0 * Pu / (1.0 + Pu), rel=1e-12)
    assert out["magnet_mass_kg"] == pytest.approx(8400.0 * 1e-3 * out["magnet_length_m"], rel=1e-12)


def test_permanent_magnet_refusals():
    with pytest.raises(ValueError, match="too small for the flux"):
        mp.permanent_magnet(0.5, 0.01, 1e-3, (), 2.0, 1e-3, 1.0, 1.0, 2e6, 8400.0)
    with pytest.raises(ValueError, match="beyond the knee"):
        mp.permanent_magnet(0.1, 0.01, 1e-3, (), 1.0, 1e-3, 1.0, 1.0, 1e5, 8400.0)
    with pytest.raises(ValueError, match="mu_rec"):
        mp.permanent_magnet(0.1, 0.01, 1e-3, (), 1.0, 1e-3, 1.0, 0.9, 2e6, 8400.0)


def test_remanence_temperature_is_explicit():
    assert mp.remanence_at_T(1.0, -0.001, 20.0, 120.0) == pytest.approx(0.9, rel=1e-12)
    with pytest.raises(ValueError):
        mp.remanence_at_T(1.0, -0.02, 20.0, 120.0)


def test_ecr_resonance_field_hand_calc():
    B = mp.ecr_resonance_field_T(2.45e9, 9.1093837139e-31, 1.602176634e-19)
    assert B == pytest.approx(2 * math.pi * 2.45e9 * 9.1093837139e-31 / 1.602176634e-19, rel=1e-15)
    assert B == pytest.approx(0.08752, abs=1e-5)


# ------------------------------------------------------------------------------------------------- refusal paths
def test_no_public_function_has_default_arguments():
    for name, fn in inspect.getmembers(mp, inspect.isfunction):
        if name.startswith("_") or fn.__module__ != mp.__name__:
            continue
        for p in inspect.signature(fn).parameters.values():
            assert p.default is inspect.Parameter.empty, f"{name}({p.name}) has a default"
    for cls in (mp.ConductorMaterial, mp.CoreSegment):
        for p in inspect.signature(cls).parameters.values():
            assert p.default is inspect.Parameter.empty, f"{cls.__name__}.{p.name} has a default"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 0.0, True, "0.02", None])
def test_invalid_gap_inputs_are_refused(bad):
    with pytest.raises(ValueError):
        mp.ampere_turns(bad, 0.02, 2e-3, (), 1.0)
    with pytest.raises(ValueError):
        mp.ampere_turns(0.015, bad, 2e-3, (), 1.0)


@pytest.mark.parametrize("kw,val", [("fill_factor", 0.0), ("fill_factor", 1.0), ("fill_factor", 1.2),
                                    ("window_area_m2", 0.0), ("mean_turn_length_m", -0.1), ("NI_A", 0.0)])
def test_invalid_coil_inputs_are_refused(kw, val):
    args = dict(NI_A=100.0, window_area_m2=1e-4, fill_factor=0.5, mean_turn_length_m=0.1, material=CU, T_C=20.0)
    args[kw] = val
    with pytest.raises(ValueError):
        mp.coil_power_continuous_W(**args)


def test_other_refusals():
    with pytest.raises(ValueError, match="leakage_factor"):
        mp.ampere_turns(0.015, 0.02, 2e-3, (), 0.9)
    with pytest.raises(ValueError, match="core_segments"):
        mp.ampere_turns(0.015, 0.02, 2e-3, None, 1.0)
    with pytest.raises(ValueError, match="CoreSegment"):
        mp.ampere_turns(0.015, 0.02, 2e-3, ((0.2, 1e-3, 1000.0),), 1.0)
    with pytest.raises(ValueError, match="mu_r"):
        mp.CoreSegment("air", 0.1, 1e-3, 0.5, 1.0)
    with pytest.raises(ValueError, match="ConductorMaterial"):
        mp.coil_power_continuous_W(100.0, 1e-4, 0.5, 0.1, "copper", 20.0)
    with pytest.raises(ValueError, match="source"):
        mp.ConductorMaterial("x", 1e-8, 20.0, 0.004, 0.0, 100.0, 8000.0, "")
    for g in (-4, 57, 24.0, True):
        with pytest.raises(ValueError):
            mp.awg_diameter_m(g)
    with pytest.raises(TypeError):
        mp.ampere_turns(0.015, 0.02, 2e-3, ())       # leakage factor has no default


def test_module_is_pure_and_not_wired():
    src = (ROOT / "abep_sim" / "magnet_power.py").read_text()
    imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", src, flags=re.M)
    assert set(imports) <= {"__future__", "math", "collections.abc", "dataclasses", "numbers"}, imports
    assert "magnet_power" not in (ROOT / "abep_sim" / "archengine.py").read_text()


# ---------------------------------------------------------------------------------------------------- data file
def test_data_file_validates_against_schema(data, schema):
    errs = _validate(data, schema, schema)
    assert not errs, errs[:20]
    if importlib.util.find_spec("jsonschema") is not None:          # full validator when installed
        import jsonschema
        jsonschema.Draft202012Validator(schema).validate(data)


def test_schema_rejects_an_unsourced_or_classless_entry(data, schema):
    bad = json.loads(json.dumps(data))
    e = bad["components"]["rf_source"]["entries"][0]
    e["source_ids"] = []
    assert _validate(bad, schema, schema)
    bad = json.loads(json.dumps(data))
    bad["components"]["rf_source"]["entries"][0]["evidence_class"] = "guess"
    assert _validate(bad, schema, schema)
    bad = json.loads(json.dumps(data))
    t = next(x for x in bad["components"]["housekeeping"]["entries"] if x["value_kind"] == "tbd")
    t["tbd_requires"] = None
    assert _validate(bad, schema, schema)
    bad = json.loads(json.dumps(data))
    del bad["components"]["compressor"]
    assert _validate(bad, schema, schema)


def test_every_entry_is_sourced_or_explicit_tbd(data):
    ids = set()
    for comp in COMPONENTS:
        c = data["components"][comp]
        assert c["entries"], comp
        for e in c["entries"]:
            assert e["id"] not in ids, e["id"]
            ids.add(e["id"])
            for sid in e["source_ids"]:
                assert sid in data["sources"], (e["id"], sid)
            if e["value_kind"] == "tbd":
                assert e["value"] is None and e["evidence_class"] == "tbd" and len(e["tbd_requires"]) >= 10
                continue
            assert e["source_ids"] and e["locator"], e["id"]
            assert e["evidence_class"] in SIX | {"definition", "qualitative"}, e["id"]
            if e["value_kind"] in ("number", "range", "series", "list"):
                assert e["evidence_class"] in SIX | {"definition"}, e["id"]
            if e["evidence_class"] in ("inferred", "model-derived") and e["value_kind"] in ("number", "range", "list"):
                assert e["derivation"] is not None or e["value_kind"] == "list" or e["role"] == "load-model", e["id"]
            if e["role"] == "efficiency-candidate":
                vals = (e["value"] if e["value_kind"] == "number" else
                        [e["value"]["min"], e["value"]["max"]] if e["value_kind"] == "range" else
                        [p["efficiency"] for p in e["value"]] if e["value_kind"] == "series" else
                        [v for k, v in e["value"].items() if k in ("drain_efficiency", "PAE")])
                for v in (vals if isinstance(vals, list) else [vals]):
                    assert 0.0 < v <= 1.0, e["id"]
    for sid, s in data["sources"].items():
        assert s["url"].startswith(("https://", "git:")), sid
        assert s["accessed"] == "2026-09-26"
    used = {sid for c in data["components"].values() for e in c["entries"] for sid in e["source_ids"]}
    assert used | {"S-CODATA22"} >= set(data["sources"]), set(data["sources"]) - used


def test_components_match_boundary_contract(data):
    assert data["boundary_version"] == "bus_power_boundary_v1"
    assert tuple(data["components"]) == tuple(sorted(COMPONENTS)) or set(data["components"]) == set(COMPONENTS)
    for c in ("rf_source",):
        assert data["components"][c]["in_architectures"] == ["rf_hall"]
    for c in ("ecr_source", "ecr_magnet"):
        assert data["components"][c]["in_architectures"] == ["ecr_hall"]
    for c in COMPONENTS[:8]:
        assert data["components"][c]["in_architectures"] == ["hall_only", "rf_hall", "ecr_hall"]


def test_digitized_series_match_the_committed_extraction(data):
    rows = list(csv.DictReader(CSV_RHODES.open()))
    assert len(rows) == 54
    for e in data["components"]["hall_discharge"]["entries"]:
        if e["value_kind"] != "series":
            continue
        vout, vin = re.match(r"HD-RH24-(\d+)V-(\d+)Vin", e["id"]).groups()
        ref = [(float(r["P_out_W"]), round(float(r["efficiency_pct"]) / 100, 4)) for r in rows
               if r["V_out_V"] == vout and r["V_in_V"] == vin]
        assert [(p["P_out_W"], p["efficiency"]) for p in e["value"]] == ref
    by = {(r["V_in_V"], r["V_out_V"], r["P_out_W"]): r["efficiency_pct"] for r in rows}
    assert by[("28", "250", "1000.1")] == "89.93" and by[("28", "400", "200.1")] == "77.16"


def test_transcribed_and_derived_values(data):
    ent = {e["id"]: e for c in data["components"].values() for e in c["entries"]}
    assert ent["RF-NEWORBIT25"]["value"] == 0.92
    assert ent["RF-VOLKMAR18"]["value"] == {"min": 0.6, "max": 0.7}
    assert ent["EC-HAYABUSA-TWTA"]["value"] == pytest.approx(40 / 110, abs=5e-5)
    assert ent["EC-NAKATANI15-GAN"]["value"]["P_out_W"] == pytest.approx(10 ** 5.04 / 1000, rel=1e-3)
    assert ent["FC-MOOG-I2R"]["value"]["max"] == pytest.approx(0.14 ** 2 * 74.5, rel=1e-3)
    assert ent["EM-RESONANCE-B"]["value"]["2.45GHz_T"] == pytest.approx(0.0875235, rel=1e-6)
    assert ent["HM-REPO-25W"]["role"] == "context-only" and ent["HD-MANZELLA96-EST"]["role"] == "context-only"


def test_generated_files_are_up_to_date():
    spec = importlib.util.spec_from_file_location("build_ec", BUILD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert DATA.read_text() == mod.dumps(mod.build_data())
    assert EXAMPLE.read_text() == mod.dumps(mod.build_example(mod.build_data()))


def test_worked_example_is_labelled_and_does_not_close(data):
    ex = json.loads(EXAMPLE.read_text())
    assert "NOT predictions" in ex["label"]
    for arch in ("hall_only", "rf_hall", "ecr_hall"):
        st = ex["ledger_closure_status"][arch]
        assert st["ledger_closes_today"] is False and st["efficiency_TBD"]
    rows = ex["discharge_28Vin_measured_points"]["rows"]
    for r in rows:
        assert r["P_bus_W"] == pytest.approx(r["P_load_W"] / r["efficiency"], rel=1e-5)


def test_no_screening_candidate_or_withdrawn_hall_number_is_used(data):
    txt = DATA.read_text() + EXAMPLE.read_text()
    assert "sgb-screen" not in txt
    assert "hall_ensemble" not in txt and "HallMap" not in txt


def test_document_states_milestones_and_links_files():
    md = (EC / "ELECTRICAL_CLOSURE.md").read_text()
    for s in ("Milestone A", "Milestone B", "Milestone C", "electrical_closure_data_v1.json",
              "abep_sim/magnet_power.py", "bus_power_boundary_v1", "worked_example_v1.json"):
        assert s in md, s
