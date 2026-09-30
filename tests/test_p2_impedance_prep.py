"""Tests for the P2 ICP impedance-map instrument preparation (docs/experiments/hall_icp/p2_impedance_map/, follow-on
fo_a9_p2_impedance_prep, trigger T_A9_P2_IMPEDANCE_PREP; owner decision A9.3 authorizations.P2).

Checks: byte-for-byte reproduction by the builder; pins verified and governance never pinned; the reducer's reflection /
impedance / de-embedding / power-accounting math against closed-form cases on SYNTHETIC, clearly labelled data; every
refusal path (missing calibration, no reference plane, uncalibrated phase, P_forward used as P_plasma, hot map before the
P1 stable region); the mismatch envelope stays TBD_AFTER_IMPEDANCE_MAP; schema <-> reducer consistency; item / evidence
discipline; no open item converted to PASS; no dependency on the parallel P1 / RFQ v2 lanes.
Run: python -m pytest -q tests/test_p2_impedance_prep.py
"""
from __future__ import annotations

import cmath
import copy
import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "experiments" / "hall_icp" / "p2_impedance_map"
BUILDER = LANE / "build_p2_impedance_prep.py"
REDUCER = LANE / "p2_impedance_reducer.py"
OUT_JSON = LANE / "p2_impedance_prep_v1.json"
OUT_MD = LANE / "P2_IMPEDANCE_PREP.md"
OUT_SCHEMA = LANE / "p2_impedance_record_schema_v1.json"
SYN = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def red():
    return _load("p2_reducer_under_test", REDUCER)


@pytest.fixture(scope="module")
def mod():
    return _load("p2_builder_under_test", BUILDER)


@pytest.fixture(scope="module")
def d():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


def _sha(rel):
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ synthetic fixtures
Z0 = 50.0


def _c(z):
    return [z.real, z.imag]


def _line(theta_deg):
    th = math.radians(theta_deg)
    return (complex(math.cos(th)), 1j * Z0 * math.sin(th), 1j * math.sin(th) / Z0, complex(math.cos(th)))


def _series_shunt(zs, ys):
    return ((1 + 0j) + zs * ys, zs, ys, 1 + 0j)


def _cal(red, line, match, e00=0j, e11=0j, e10e01=1 + 0j, fix=(1 + 0j, 0j, 0j, 1 + 0j)):
    def sp(abcd, a, b):
        s11, s12, s21, s22 = red.abcd_to_s(abcd, Z0)
        return {"from_plane": a, "to_plane": b, "S11": _c(s11), "S12": _c(s12), "S21": _c(s21), "S22": _c(s22),
                "cal_id": "SYN-2P", "phase_calibrated": True}
    return {"schema": red.CAL_SCHEMA_ID, "calibration_set_id": "SYN", "data_class": "synthetic_test", "f_Hz": 13.56e6,
            "Z0_ohm": Z0, "power_sensors": {"PS": {"CF_fwd": 1.0, "CF_ref": 1.0, "certificate": "SYNTHETIC"}},
            "coupler": {"cal_id": "CPL", "plane": "RP-CPL", "phase_calibrated": True, "e00": _c(e00), "e11": _c(e11),
                        "e10e01": _c(e10e01)},
            "two_ports": {"line": sp(line, "RP-CPL", "RP-MIN"), "match_states": {"TS1": sp(match, "RP-MIN", "RP-ANT")}},
            "vi_probe": {"cal_id": "VI", "phase_calibrated": True, "k_V": [1.0, 0.0], "k_I": [1.0, 0.0],
                         "fixture_abcd": [[_c(fix[0]), _c(fix[1])], [_c(fix[2]), _c(fix[3])]],
                         "fixture_from_plane": "RP-VI", "fixture_to_plane": "RP-ANT", "amplitude_convention": "peak"},
            "loss_bounds": {"LB1": {"loss_fraction_max": 0.1, "source": "SYNTHETIC", "evidence_class": "assumed"}},
            "cold_references": {"CR1": {"R_cold_ohm": 1.5, "source_record_id": "SYN-COLD", "evidence_class": "measured",
                                        "antenna_temperature_K": 300.0}},
            "antenna_current_probe": {"cal_id": "ACP", "k_mag": 1.0, "certificate": "SYNTHETIC"}}


def _rec(red, cal, z_ant, p_fwd=100.0, phase="DUMMY_LOAD"):
    tp = cal["two_ports"]
    net = red.cascade(red.s_to_abcd(*[red.cx(tp["line"][k], k) for k in ("S11", "S12", "S21", "S22")], Z0),
                      red.s_to_abcd(*[red.cx(tp["match_states"]["TS1"][k], k) for k in ("S11", "S12", "S21", "S22")],
                                    Z0))
    g_in = red.gamma_from_z(red.z_in(net, z_ant), Z0)
    cc = cal["coupler"]
    e00, e11, e10e01 = (red.cx(cc[k], k) for k in ("e00", "e11", "e10e01"))
    m = e00 + e10e01 * g_in / (1 - e11 * g_in)
    fx = cal["vi_probe"]["fixture_abcd"]
    a, b, c, dd = (red.cx(fx[0][0], "A"), red.cx(fx[0][1], "B"), red.cx(fx[1][0], "C"), red.cx(fx[1][1], "D"))
    v_a, i_a = z_ant * (2 + 0j), 2 + 0j
    return {"schema": red.SCHEMA_ID, "record_id": "SYN-1", "data_class": "synthetic_test", "phase": phase,
            "calibration_set_id": "SYN", "f_Hz": 13.56e6, "Z0_ohm": Z0,
            "reference_planes": {"coupler_powers": "RP-CPL", "coupler_reflection": "RP-CPL", "vi_probe": "RP-VI"},
            "methods": ["vi_probe", "deembed"], "loss_method": "two_port",
            "coupler": {"P_sens_fwd_W": p_fwd, "P_sens_ref_W": p_fwd * abs(g_in) ** 2, "power_sensor_cal_id": "PS",
                        "reflection_raw": _c(m)},
            "vi_probe": {"V_raw": _c(a * v_a + b * i_a), "I_raw": _c(c * v_a + dd * i_a), "vi_cal_id": "VI"},
            "match_state": {"tuning_state_id": "TS1", "positions": {}, "auto_tune": False, "loss_bound_id": "LB1"},
            "factors": {k: None for k in red.REQUIRED_FACTOR_FIELDS},
            "plasma_state": {"lit": False, "mode": "UNLIT", "optical_signal_V": None},
            "sweep": {"sweep_id": "S", "direction": "single", "index": 0}, "settling": {"dwell_s": None, "settled": None},
            "temperatures_K": {}, "cold_reference_id": None, "p1_stable_region_ref": None, "antenna_current": None}


@pytest.fixture()
def case(red):
    cal = _cal(red, _line(30.0), _series_shunt(complex(0.5, -80.0), complex(0.0002, 0.012)),
               e00=complex(0.01, -0.02), e11=complex(0.03, 0.01), e10e01=complex(0.98, 0.05),
               fix=(1 + 0j, complex(0.05, 3.0), 0j, 1 + 0j))
    return cal, _rec(red, cal, complex(2.0, 80.0))


# ------------------------------------------------------------------------------------------------ reproduction / pins
def test_builder_reproduces_outputs(mod):
    js, md, sc = mod.render()
    assert OUT_JSON.read_text(encoding="utf-8") == js
    assert OUT_MD.read_text(encoding="utf-8") == md
    assert OUT_SCHEMA.read_text(encoding="utf-8") == sc
    assert mod.main(["--check"]) == 0


def test_pins_verified_and_governance_never(d):
    for p in d["decision_pins"] + d["deliverable_pins"]:
        assert _sha(p["path"]) == p["sha256"], p["path"]
    paths = {p["path"] for p in d["decision_pins"]}
    for need in ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
                 "docs/decisions/OD_2026_09_29_owner_answers_147.json",
                 "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
                 "docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json",
                 "docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json",
                 "docs/decisions/OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md"):
        assert need in paths
    pinned = paths | {p["path"] for p in d["deliverable_pins"]}
    for g in ("lane_registry_v1.json", "trigger_registry_v1.json", "runtime_state.json", ".jsonl"):
        assert not any(g in p for p in pinned), g


def test_owner_row_hashes_recompute(d):
    ans = json.loads((REPO / "docs/decisions/OD_2026_09_29_owner_answers_147.json").read_text(encoding="utf-8"))
    by = {a["row"]: a for a in ans["answers"]}
    n = 0
    for o in d["owner_answers_applied"]:
        r = o["ref"]
        if isinstance(r, dict) and r.get("kind") == "owner_row":
            h = hashlib.sha256(by[r["row"]]["owner_answer_verbatim"].encode("utf-8")).hexdigest()
            assert r["answer_sha256"] == h
            n += 1
    assert n >= 10


# ------------------------------------------------------------------------------------------------ closed-form math
def test_gamma_vswr_closed_form(red):
    g = red.gamma_from_z(complex(20, 50), Z0)
    assert abs(g) == pytest.approx(0.6778, abs=5e-4)
    assert red.vswr(abs(g)) == pytest.approx(5.208, abs=2e-3)
    assert red.gamma_from_z(complex(50, 0), Z0) == 0
    assert red.vswr(0.0) == 1.0
    assert red.gamma_from_z(0j, Z0) == -1
    assert red.z_from_gamma(red.gamma_from_z(complex(20, 50), Z0), Z0) == pytest.approx(complex(20, 50))
    assert red.gamma_mag_from_powers(100.0, 25.0) == pytest.approx(0.5)
    with pytest.raises(red.RecordError):
        red.vswr(1.0)


def test_selfcheck_matches_a9_07_review_case(d):
    sc = {s["id"]: s for s in d["reducer_selfcheck"]}
    assert sc["SC-01"]["agrees_to_4_significant_digits"] is True
    assert sc["SC-02"]["recovered_vi_probe"] == pytest.approx([2.0, 80.0], abs=1e-6)
    assert sc["SC-02"]["recovered_deembed"] == pytest.approx([2.0, 80.0], abs=1e-6)
    assert sc["SC-02"]["match_line_efficiency_abcd"] == pytest.approx(sc["SC-02"]["match_line_efficiency_s_formula"])
    assert sc["SC-03"]["closes"] is True
    assert all(s["evidence_status"] == SYN for s in d["reducer_selfcheck"])


def test_abcd_s_roundtrip_and_deembed_lossless_line(red):
    net = _line(37.0)
    s = red.abcd_to_s(net, Z0)
    assert abs(s[0]) < 1e-12 and abs(s[3]) < 1e-12
    assert s[2] == pytest.approx(cmath.exp(-1j * math.radians(37.0)))
    back = red.s_to_abcd(*s, Z0)
    assert all(x == pytest.approx(y) for x, y in zip(back, net))
    zl = complex(12.0, -30.0)
    gl = red.gamma_from_z(zl, Z0)
    gin = red.gamma_from_z(red.z_in(net, zl), Z0)
    assert gin == pytest.approx(gl * cmath.exp(-2j * math.radians(37.0)))       # closed form for a matched line
    assert red.deembed_load(net, red.z_in(net, zl)) == pytest.approx(zl)
    assert red.transfer_efficiency(net, zl) == pytest.approx(1.0)
    ident = (1 + 0j, 0j, 0j, 1 + 0j)
    assert red.deembed_load(ident, zl) == pytest.approx(zl)


def test_attenuator_efficiency_closed_form(red):
    a = 0.8                                                  # matched attenuator: S21 = S12 = a, S11 = S22 = 0
    net = red.s_to_abcd(0j, a + 0j, a + 0j, 0j, Z0)
    assert red.transfer_efficiency(net, complex(Z0, 0)) == pytest.approx(a ** 2)


def test_efficiency_abcd_equals_s_formula(red):
    net = red.cascade(_line(20.0), _series_shunt(complex(0.7, -60.0), complex(0.0003, 0.01)))
    s11, s12, s21, s22 = red.abcd_to_s(net, Z0)
    for zl in (complex(2, 80), complex(20, 50), complex(0.4, 30)):
        gl = red.gamma_from_z(zl, Z0)
        gi = s11 + s12 * s21 * gl / (1 - s22 * gl)
        eta = abs(s21) ** 2 * (1 - abs(gl) ** 2) / (abs(1 - s22 * gl) ** 2 * (1 - abs(gi) ** 2))
        assert red.transfer_efficiency(net, zl) == pytest.approx(eta)


def test_error_model_and_fixture_closed_form(red):
    e00, e11, e10e01 = complex(0.02, 0.01), complex(-0.03, 0.02), complex(0.95, -0.1)
    g = complex(0.3, -0.4)
    m = e00 + e10e01 * g / (1 - e11 * g)
    assert red.correct_reflection(m, e00, e11, e10e01) == pytest.approx(g)
    zs = complex(0.1, 5.0)                                   # series fixture: Z_ant = V_p / I_p - Z_s
    v_a, i_a = red.fixture_to_plane((1 + 0j, zs, 0j, 1 + 0j), complex(100, 20), complex(1, -0.5))
    assert v_a / i_a == pytest.approx(complex(100, 20) / complex(1, -0.5) - zs)


def test_reduce_record_both_methods_and_power_accounting(red, case):
    cal, rec = case
    out = red.reduce_record(rec, {"SYN": cal})
    for m in ("vi_probe", "deembed"):
        assert out["Z_antenna"][m]["R_ohm"] == pytest.approx(2.0, abs=1e-6)
        assert out["Z_antenna"][m]["X_ohm"] == pytest.approx(80.0, abs=1e-6)
        assert out["Z_antenna"][m]["plane"] == "RP-ANT"
    assert out["Z_antenna_primary_method"] == "vi_probe"
    c = out["at_RP_CPL"]
    assert c["P_net_W"] == pytest.approx(c["P_forward_W"] - c["P_reflected_W"])
    assert c["gamma_mag_complex"] == pytest.approx(c["gamma_mag_from_powers"], abs=1e-6)
    assert c["P_forward_W"] - c["P_reflected_W"] - out["P_line_match_loss_W"] == pytest.approx(out["P_delivered_W"])
    assert out["P_delivered_W"] < c["P_net_W"] < c["P_forward_W"]           # never P_forward = P_delivered / plasma
    assert out["evidence_status"] == SYN


def test_declared_bound_and_not_available(red, case):
    cal, rec = case
    r = copy.deepcopy(rec)
    r["loss_method"] = "declared_bound"
    out = red.reduce_record(r, {"SYN": cal})
    pn = out["at_RP_CPL"]["P_net_W"]
    assert out["P_delivered_W"]["max"] == pytest.approx(pn)
    assert out["P_delivered_W"]["min"] == pytest.approx(0.9 * pn)
    r["loss_method"] = "not_available"
    out = red.reduce_record(r, {"SYN": cal})
    assert isinstance(out["P_delivered_W"], str) and out["P_delivered_W"].startswith("TBD")


def test_resistance_split_and_antenna_current(red, case):
    cal, rec = case
    r = copy.deepcopy(rec)
    r["cold_reference_id"] = "CR1"
    r["antenna_current"] = {"I_rms_A": 2.0, "probe_cal_id": "ACP"}
    out = red.reduce_record(r, {"SYN": cal})
    sp = out["resistance_split"]
    assert sp["R_plasma_ohm"] == pytest.approx(0.5)
    assert sp["eta_transfer"] == pytest.approx(0.25)
    assert sp["evidence_class"] == "reconstructed"
    assert out["antenna_current_check"]["R_total_from_P_delivered_ohm"] == pytest.approx(out["P_delivered_W"] / 4.0)


def test_mismatch_envelope_stays_tbd_after_impedance_map(red, case):
    cal, rec = case
    out = red.reduce_record(rec, {"SYN": cal})
    env = red.mismatch_envelope([out], ["DUMMY_LOAD"])
    assert env["rating_status"] == "TBD_AFTER_IMPEDANCE_MAP"
    assert env["evidence_status"] == SYN
    c = out["at_RP_CPL"]
    v, i = red.line_peak_stress(c["P_forward_W"], c["gamma_mag_from_powers"], Z0)
    assert env["line_V_peak_max_V"] == pytest.approx(v, rel=1e-6)
    assert v == pytest.approx(math.sqrt(2 * c["P_forward_W"] * Z0) * (1 + c["gamma_mag_from_powers"]))
    with pytest.raises(red.RecordError):
        red.mismatch_envelope([out], [])
    with pytest.raises(red.RecordError):
        red.mismatch_envelope([out], ["HOT_MAP"])                     # zero records selected


# ------------------------------------------------------------------------------------------------ refusal paths
def _raises(red, exc, rec, cals):
    with pytest.raises(exc):
        red.reduce_record(rec, cals)


def test_refuses_missing_calibration(red, case):
    cal, rec = case
    _raises(red, red.MissingCalibrationError, rec, {})
    r = copy.deepcopy(rec)
    r["coupler"]["power_sensor_cal_id"] = "NOPE"
    _raises(red, red.MissingCalibrationError, r, {"SYN": cal})
    c2 = copy.deepcopy(cal)
    c2["f_Hz"] = 27.12e6
    _raises(red, red.MissingCalibrationError, rec, {"SYN": c2})
    r = copy.deepcopy(rec)
    r["match_state"]["tuning_state_id"] = "TS-UNCHARACTERIZED"
    _raises(red, red.MissingCalibrationError, r, {"SYN": cal})
    c3 = copy.deepcopy(cal)
    del c3["coupler"]["e00"]
    _raises(red, red.MissingCalibrationError, rec, {"SYN": c3})
    c4 = copy.deepcopy(cal)
    c4["vi_probe"]["fixture_abcd"] = None
    _raises(red, red.MissingCalibrationError, rec, {"SYN": c4})
    c5 = copy.deepcopy(cal)
    del c5["power_sensors"]
    _raises(red, red.MissingCalibrationError, rec, {"SYN": c5})


def test_refuses_missing_or_wrong_reference_plane(red, case):
    cal, rec = case
    r = copy.deepcopy(rec)
    del r["reference_planes"]
    _raises(red, red.ReferencePlaneError, r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["reference_planes"] = {}
    _raises(red, red.ReferencePlaneError, r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["reference_planes"]["coupler_powers"] = "RP-ANT"                 # A9.2: powers on the 50-ohm side only
    _raises(red, red.ReferencePlaneError, r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["reference_planes"]["vi_probe"] = "RP-XYZ"
    _raises(red, red.ReferencePlaneError, r, {"SYN": cal})
    r = copy.deepcopy(rec)
    del r["reference_planes"]["coupler_reflection"]
    _raises(red, red.ReferencePlaneError, r, {"SYN": cal})
    c2 = copy.deepcopy(cal)
    c2["two_ports"]["line"]["to_plane"] = "RP-ANT"
    _raises(red, red.ReferencePlaneError, rec, {"SYN": c2})


def test_refuses_uncalibrated_phase(red, case):
    cal, rec = case
    r = copy.deepcopy(rec)
    r["coupler"]["reflection_raw"] = None                             # scalar powers only -> no de-embedding
    _raises(red, red.UncalibratedPhaseError, r, {"SYN": cal})
    c2 = copy.deepcopy(cal)
    c2["coupler"]["phase_calibrated"] = False
    _raises(red, red.UncalibratedPhaseError, rec, {"SYN": c2})
    c3 = copy.deepcopy(cal)
    c3["vi_probe"]["phase_calibrated"] = False
    _raises(red, red.UncalibratedPhaseError, rec, {"SYN": c3})
    c4 = copy.deepcopy(cal)
    c4["two_ports"]["match_states"]["TS1"]["phase_calibrated"] = False
    _raises(red, red.UncalibratedPhaseError, rec, {"SYN": c4})
    r = copy.deepcopy(rec)                                            # scalar-only record without de-embedding is fine
    r["coupler"]["reflection_raw"] = None
    r["methods"] = ["vi_probe"]
    assert red.reduce_record(r, {"SYN": cal})["Z_antenna_primary_method"] == "vi_probe"


def test_refuses_forward_as_plasma(red, case):
    cal, rec = case
    r = copy.deepcopy(rec)
    r["P_plasma_W"] = r["coupler"]["P_sens_fwd_W"]
    _raises(red, red.ForwardAsPlasmaError, r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["factors"]["P_absorbed_plasma_W"] = 10.0
    _raises(red, red.ForwardAsPlasmaError, r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["power_labels"] = {"P_forward_W": "P_plasma"}
    _raises(red, red.ForwardAsPlasmaError, r, {"SYN": cal})


def test_refuses_hot_map_before_p1_region(red, case):
    cal, rec = case
    for ref in (None, "", "PENDING docs/experiments/hall_icp/p1_icp_bench/", "TBD"):
        r = copy.deepcopy(rec)
        r["phase"] = "HOT_MAP"
        r["p1_stable_region_ref"] = ref
        _raises(red, red.SequenceError, r, {"SYN": cal})


def test_refuses_inconsistent_values(red, case):
    cal, rec = case
    r = copy.deepcopy(rec)
    r["coupler"]["P_sens_ref_W"] = r["coupler"]["P_sens_fwd_W"] * 1.1
    _raises(red, red.RecordError, r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["coupler"]["P_sens_fwd_W"] = float("nan")
    _raises(red, red.RecordError, r, {"SYN": cal})
    r = copy.deepcopy(rec)
    del r["factors"]["P_mains_in_W"]
    _raises(red, red.RecordError, r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["methods"] = ["guess"]
    _raises(red, red.RecordError, r, {"SYN": cal})


# ------------------------------------------------------------------------------------------------ schema / data model
def test_schema_matches_reducer(red, d):
    sc = json.loads(OUT_SCHEMA.read_text(encoding="utf-8"))
    assert sc["required"] == list(red.REQUIRED_RECORD_FIELDS)
    assert sc["$defs"]["calibration_set"]["required"] == list(red.REQUIRED_CAL_FIELDS)
    for f in red.REQUIRED_RECORD_FIELDS:
        p = sc["properties"][f]
        assert p["description"] and "x-units" in p and "x-reference-plane" in p
    assert d["data_model"]["required_record_fields"] == list(red.REQUIRED_RECORD_FIELDS)
    assert set(d["data_model"]["refusals"]) >= {"MissingCalibrationError", "ReferencePlaneError",
                                                 "UncalibratedPhaseError", "ForwardAsPlasmaError", "SequenceError"}


# ------------------------------------------------------------------------------------------------ content discipline
def test_items_fields_and_vocabularies(mod, d):
    ids = [it["id"] for it in d["items"]]
    assert len(ids) == len(set(ids))
    for it in d["items"]:
        for k in ("id", "name", "value", "units", "basis", "source", "evidence_class", "status", "freeze_point"):
            assert k in it, (it["id"], k)
        assert it["freeze_point"] in mod.FREEZE_POINTS, it["id"]
        assert it["status"] in mod.STATUSES, it["id"]
        assert it["source"], it["id"]
        v = it["value"]
        numeric = isinstance(v, (int, float)) or (isinstance(v, list) and v and all(isinstance(x, (int, float))
                                                                                     for x in v))
        if numeric:
            assert it["evidence_class"] in mod.EVIDENCE_CLASSES, it["id"]
        if isinstance(v, str) and v.startswith("TBD"):
            assert "requires" in v and it["evidence_class"] is None, it["id"]
        if it["evidence_class"] is not None:
            assert it["evidence_class"] in mod.EVIDENCE_CLASSES, it["id"]
    for need in ("RP-CPL", "RP-ANT", "RP-MIN", "CAL-P2-05", "CAL-P2-07", "CAL-P2-08", "HM-R01", "HM-R05", "HM-R06",
                 "INS-P2-01", "INS-P2-04", "UB-P2-Z-02"):
        assert need in ids


def test_owner_values_and_statuses_unchanged(d):
    a92 = json.loads((REPO / "docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json")
                     .read_text(encoding="utf-8"))["decisions"]
    assert d["a9_2_statuses_carried"] == a92["a9_10_statuses"]
    items = {it["id"]: it for it in d["items"]}
    assert items["P2-F-01"]["value"] == 13.56 and items["P2-F-01"]["units"] == "MHz"
    chain = {it["id"]: it for it in d["chain_parameters"]}
    assert items["P2-F-03"]["value"] == [0.0, 500.0] and "TBD_AFTER_IMPEDANCE_MAP" in chain["P2-F-03"]["rating"]
    txt = json.dumps(d)
    assert '"PASS"' not in txt and "thermal closure PASS" not in txt
    for o in d["p2_outputs_later"]:
        assert "PASS" not in o["status"]
    outs = {o["id"]: o for o in d["p2_outputs_later"]}
    for q in ("ICPQ-10", "ICPQ-11", "OQ-A910-06"):
        assert outs[q]["status"].startswith("OPEN")
    assert outs["RF_COMPONENT_RATINGS"]["status"] == "TBD_AFTER_IMPEDANCE_MAP"


def test_analog_values_copied_not_typed(d):
    ev = json.loads((REPO / "docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json").read_text(encoding="utf-8"))
    by = {e["id"]: e for e in ev["extraction"]}
    for t in d["published_analog_context"]:
        assert t["value"] == by[t["id"]]["value"] and t["locator"] == by[t["id"]]["locator"]
        assert "never a Vyovrinda" in t["use_here"]


def test_new_questions_are_new_and_answerable(d):
    st = json.loads((REPO / "docs/budgets/owner_decisions/owner_questions_state_v3.json").read_text(encoding="utf-8"))
    existing = {r["id"] for r in st["rows"]}
    for q in d["open_owner_questions"]:
        assert q["id"] not in existing
        assert q["proposed_answer"] and q["needed_by"]


def test_interface_demands_both_directions_and_pending_lanes(d):
    dirs = {x["direction"] for x in d["interface_demands"]}
    assert "P1 -> P2" in dirs and "P2 -> P1" in dirs
    assert any("RFQ v2" in x for x in dirs)
    pend = {p["path"] for p in d["pending_lanes"]}
    assert pend == {"docs/experiments/hall_icp/p1_icp_bench/", "docs/procurement/rfq_a9_v2/"}
    for inst in d["instrument_list"]:
        assert inst["rfq_v2_line"].startswith("PENDING docs/procurement/rfq_a9_v2/")


def test_m16_rows_and_sections_present(d):
    assert {m["row"] for m in d["m16_impact"]} == {15, 17, 18, 19}
    for k in ("interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse", "m16_impact",
              "h3_h4_inputs", "calibration_plan", "hot_map_methodology", "data_model", "instrument_list",
              "p2_outputs_later", "reference_planes", "z_antenna_methods", "z_antenna_recommendation"):
        assert d[k], k
    for h in d["historical_reuse"]:
        assert _sha(h["path"]) == h["sha256"]


def test_code_hygiene():
    for p in (BUILDER, REDUCER):
        src = p.read_text(encoding="utf-8")
        assert "xe" + "_ledger" not in src, p.name
        assert "import archengine" not in src and "from abep_sim" not in src and "import abep_sim" not in src
        assert "plasma_devices" not in src
        for lane in ("p1_icp_bench", "rfq_a9_v2"):
            assert not re.search(r"open\([^)]*" + lane, src) and "import " + lane not in src
    red_src = REDUCER.read_text(encoding="utf-8")
    imports = re.findall(r"^(?:from|import) (\w+)", red_src, re.M)
    assert set(imports) <= {"__future__", "cmath", "math"}
    test_src = Path(__file__).read_text(encoding="utf-8")
    assert "xe" + "_ledger" not in test_src.replace('"xe" + "_ledger"', "")


def test_no_winner_or_prediction_vocabulary(d):
    txt = (json.dumps(d) + OUT_MD.read_text(encoding="utf-8")).lower()
    for banned in ("winner:", "best architecture", "recommended architecture", "sgb-screen", "ensemble_member_id",
                   "predicted thrust", "predicted impedance"):
        assert banned not in txt, banned


def test_lane_dir_contents():
    names = sorted(p.name for p in LANE.iterdir() if p.name != "__pycache__")
    assert names == sorted(["build_p2_impedance_prep.py", "p2_impedance_reducer.py", "p2_impedance_prep_v1.json",
                            "P2_IMPEDANCE_PREP.md", "p2_impedance_record_schema_v1.json"])
