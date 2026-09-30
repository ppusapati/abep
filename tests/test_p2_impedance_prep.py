"""Tests for the P2 ICP impedance-map instrument preparation (docs/experiments/hall_icp/p2_impedance_map/, follow-on
fo_a9_p2_impedance_prep, trigger T_A9_P2_IMPEDANCE_PREP; owner decision A9.3 authorizations.P2).

Checks: byte-for-byte reproduction by the builder; pins verified and governance never pinned; the reducer's reflection /
impedance / de-embedding / power-accounting math against closed-form cases on SYNTHETIC, clearly labelled data; every
refusal path (missing calibration, no reference plane, uncalibrated phase, P_forward used as P_plasma, hot map before the
P1 stable region); the mismatch envelope stays TBD_AFTER_IMPEDANCE_MAP; schema <-> reducer consistency; item / evidence
discipline; no open item converted to PASS; merged P1 / RFQ v2 ids cross-checked (A9.5 execution); owner A9.4 P2Q-05
(photodiode required; UNLIT / E_MODE / H_MODE / UNCERTAIN) incorporated by fo_a9_4_incorporation.
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


POS = {"C_series": "SYN-1", "C_shunt": "SYN-1"}
LV = {"verification_id": "SYN-LV-01", "status": "LOSS_MODEL_VERIFIED", "method": "CAL-P2-09_calorimetric_at_power",
      "evidence_record_ids": ["SYN-CALORIMETRY-01"], "tuning_states": ["TS1"], "data_class": "synthetic_test"}


def _cal(red, line, match, e00=0j, e11=0j, e10e01=1 + 0j, fix=(1 + 0j, 0j, 0j, 1 + 0j)):
    def sp(abcd, a, b):
        s11, s12, s21, s22 = red.abcd_to_s(abcd, Z0)
        return {"from_plane": a, "to_plane": b, "S11": _c(s11), "S12": _c(s12), "S21": _c(s21), "S22": _c(s22),
                "cal_id": "SYN-2P", "phase_calibrated": True, "positions": dict(POS)}
    return {"schema": red.CAL_SCHEMA_ID, "calibration_set_id": "SYN", "data_class": "synthetic_test", "f_Hz": 13.56e6,
            "Z0_ohm": Z0, "power_sensors": {"PS": {"CF_fwd": 1.0, "CF_ref": 1.0, "certificate": "SYNTHETIC"}},
            "coupler": {"cal_id": "CPL", "plane": "RP-CPL", "phase_calibrated": True, "e00": _c(e00), "e11": _c(e11),
                        "e10e01": _c(e10e01)},
            "two_ports": {"line": sp(line, "RP-CPL", "RP-MIN"), "match_states": {"TS1": sp(match, "RP-MIN", "RP-ANT")}},
            "vi_probe": {"cal_id": "VI", "phase_calibrated": True, "k_V": [1.0, 0.0], "k_I": [1.0, 0.0],
                         "fixture_abcd": [[_c(fix[0]), _c(fix[1])], [_c(fix[2]), _c(fix[3])]],
                         "fixture_from_plane": "RP-VI", "fixture_to_plane": "RP-ANT", "amplitude_convention": "peak"},
            "loss_bounds": {"LB1": {"loss_fraction_max": 0.1, "source": "SYNTHETIC", "evidence_class": "assumed",
                                    "verification": dict(LV, verification_id="SYN-LV-LB1", tuning_states=[])}},
            "cold_references": {"CR1": {"R_cold_ohm": 1.5, "source_record_id": "SYN-COLD",
                                        "source_phase": "CAL-P2-08_VNA_UNPOWERED",
                                        "unlit_verification": {"basis": "SYNTHETIC CAL-P2-08 VNA record"},
                                        "evidence_class": SYN, "antenna_temperature_K": 300.0}},
            "antenna_current_probe": {"cal_id": "ACP", "k_mag": 1.0, "certificate": "SYNTHETIC"},
            "loss_verification": dict(LV)}


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
            "match_state": {"tuning_state_id": "TS1", "positions": dict(POS), "auto_tune": False,
                            "loss_bound_id": "LB1"},
            "factors": {k: None for k in red.REQUIRED_FACTOR_FIELDS},
            "plasma_state": {"lit": False, "mode": "UNLIT", "optical_signal_V": None, "unlit_threshold_V": None,
                             "unlit_threshold_source": None, "threshold_basis": None,
                             "photodiode_line_of_sight_ok": None, "photodiode_saturated": None,
                             "electrical_ignition_or_mode_transition": None, "electrical_indicator_basis": None},
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
    js, md, sc, ms = mod.render()
    assert OUT_JSON.read_text(encoding="utf-8") == js
    assert OUT_MD.read_text(encoding="utf-8") == md
    assert OUT_SCHEMA.read_text(encoding="utf-8") == sc
    assert (LANE / "p2_impedance_map_schema_v1.json").read_text(encoding="utf-8") == ms
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


def test_interface_demands_both_directions_and_merged_lanes(d):
    """A9.5 execution (carried A9.4 minor): the P1 bench and RFQ v2 packages are merged; stale 'PENDING <path>'
    references are replaced by their real ids, which must exist in the merged files."""
    dirs = {x["direction"] for x in d["interface_demands"]}
    assert "P1 -> P2" in dirs and "P2 -> P1" in dirs
    assert any("RFQ v2" in x for x in dirs)
    assert "pending_lanes" not in d
    merged = {p["path"] for p in d["merged_lanes"]}
    assert merged == {"docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
                      "docs/procurement/rfq_a9_v2/rfq_a9_v2.json"}
    txt = json.dumps(d) + OUT_MD.read_text(encoding="utf-8")
    assert "PENDING docs/experiments/hall_icp/p1_icp_bench/" not in txt
    assert "PENDING docs/procurement/rfq_a9_v2/" not in txt
    rfq2 = (REPO / "docs/procurement/rfq_a9_v2/rfq_a9_v2.json").read_text(encoding="utf-8")
    p1 = (REPO / "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json").read_text(encoding="utf-8")
    for inst in d["instrument_list"]:
        v = inst["rfq_v2_line"]
        assert "PENDING" not in v and v.endswith("(docs/procurement/rfq_a9_v2/rfq_a9_v2.json)"), inst["id"]
        ids = re.findall(r"\b(?:RF|GAS|VAC|HE|ME|TH)-[LO]\d\d\b", v)
        assert ids or v.startswith("no RFQ v2 line"), inst["id"]
        for i in ids:
            assert f'"{i}"' in rfq2, (inst["id"], i)
    for i in d["merged_ids_cited"]["docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json"]:
        assert f'"{i}"' in p1, i
    for i in d["merged_ids_cited"]["docs/procurement/rfq_a9_v2/rfq_a9_v2.json"]:
        assert f'"{i}"' in rfq2, i
    idem = {x["id"]: x for x in d["interface_demands"]}
    assert idem["IDP2-01"]["xref"][0]["counterpart"] == "P1:IF-P1-01"
    assert idem["IDP2-17"]["xref"][0]["counterpart"] == "P1:IF-P1-23"
    assert "TH-L07" in idem["IDP2-18"]["status"] and idem["IDP2-05"]["xref"][0]["counterpart"] == "RFQ:IFD-13"
    assert d["rfq_v2_coverage_checked"]["INS-P2-04"] == ["RF-L13"]     # equals RFQ v2 instrument_coverage (XL-12)


def test_a95_ins_p2_10_and_pins(d):
    ins = {i["id"]: i for i in d["instrument_list"]}
    p10 = ins["INS-P2-10"]
    assert any(isinstance(s_, dict) and s_.get("kind") == "A9.4" and s_.get("decision") == "P2Q-05"
               for s_ in p10["source"])
    assert p10["evidence_class"] == "owner-stated" and "A9.4 P2Q-05" in p10["basis"]
    for need in ("TH-L07", "TH-L08", "VAC-L07"):
        assert need in p10["rfq_v2_line"], need
    assert ins["INS-P2-02"]["rfq_v2_line"].startswith("RF-L02") and ins["INS-P2-11"]["rfq_v2_line"].startswith("RF-L11")
    assert ins["INS-P2-04"]["rfq_v2_line"].startswith("RF-L13")      # RFQ v2 completion added the VNA line
    items = {it["id"]: it for it in d["items"]}
    assert items["INS-P2-10"]["evidence_class"] == "owner-stated"
    pins = {p["path"]: p["sha256"] for p in d["decision_pins"] + d["deliverable_pins"]}
    assert pins["docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json"] == \
        "c9e101f2c409c2d28ad256818c22f13ee801bc532d7e4ef470f375d7bb1fe1d3"
    assert pins["docs/decisions/OD_2026_09_30_A9_5_P1_CLOSURE_OWNER_DECISIONS.md"] == \
        "9e49e923328441c1fc82afd3eb64c13d85fc818e8fe534576ada61a16fa525f3"
    assert "docs/procurement/rfq_a9_v2/rfq_a9_v2.json" not in pins   # RFQ v2 reads P2: ids checked, a pin would be circular
    assert not any("p1_icp_bench" in p_ for p_ in pins)                  # same follow-on lane: checked, not pinned
    inc = d["a9_5_incorporation"]
    assert inc["follow_on"] == "fo_a9_5_closure_rule" and inc["base_commit"] == \
        "71f31b2a254fe01059b130b554b97c7584ae6b30"
    applied = [o for o in d["owner_answers_applied"] if isinstance(o["ref"], dict) and o["ref"].get("kind") == "A9.5"]
    assert applied and "INS-P2-10" in applied[0]["how"]


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
                            "P2_IMPEDANCE_PREP.md", "p2_impedance_record_schema_v1.json", "p2_framework.py",
                            "p2_impedance_map_schema_v1.json"])


# ------------------------------------------------------------------------------------------------ repair-round checks
A93_IDS = {"OQ-VI-03", "OQ-VI-05", "OQ-A907-02", "ICPQ-06", "OQ-RFQ-06", "OQ-RFQ-07", "OQ-RFQ-02", "OQ-RFQ-10"}


def test_every_a93_decision_dispositioned(d):
    a93 = json.loads((REPO / "docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json")
                     .read_text(encoding="utf-8"))
    assert set(a93["decisions"]) == A93_IDS
    done = {o["ref"]["decision"] for o in d["owner_answers_applied"]
            if isinstance(o["ref"], dict) and o["ref"].get("kind") == "A9.3"}
    assert A93_IDS <= done, A93_IDS - done
    md = OUT_MD.read_text(encoding="utf-8")
    sec_c = md.split("## (c) Owner answers applied")[1].split("## (d)")[0]
    for i in A93_IDS:
        assert f"A9.3 {i}" in sec_c, i
    hm = {x["id"]: x for x in d["hot_map_methodology"]["factors"]}
    assert "ICPQ-06" in hm["HM-F07"]["value"] and "OQ-RFQ-02" in hm["HM-F02"]["value"]
    assert "I_d,max,H1" in hm["HM-F06"]["value"]
    assert hm["HM-F01"]["evidence_class"] == "owner-allocation"
    ids = {x["id"]: x for x in d["interface_demands"]}
    assert "I_d,max,H1" in ids["IDP2-10"]["quantity"] and "ICPQ-06" in ids["IDP2-15"]["quantity"]
    assert "OQ-RFQ-02" in ids["IDP2-14"]["quantity"]


def test_sequence_order_and_powered_prerequisites(d):
    seq = d["hot_map_methodology"]["sequence"]
    order = [s["step"] for s in seq]
    assert order == [f"S-{i:02d}" for i in range(len(seq))]
    pos = {}
    for s in seq:
        for m in re.finditer(r"CAL-P2-(\d+)((?:/\d+)*)", s["what"]):
            for c in [m.group(1)] + [x for x in m.group(2).split("/") if x]:
                pos.setdefault(int(c), order.index(s["step"]))
    assert pos[8] < pos[10]                       # cold antenna impedance before the simulator validation
    assert pos[7] < pos[15] and pos[9] < pos[15]  # known power (calorimetry) before at-power V/I verification
    rules = {r["id"]: r for r in d["hot_map_methodology"]["rules"]}
    assert "HM-R13" in rules and "pre-tuned" in rules["HM-R13"]["value"] and "ICP-16" in rules["HM-R13"]["value"]
    for s in seq:
        assert isinstance(s["powered"], bool)
        if s["powered"]:
            assert "HM-R13" in s["prerequisites"], s["step"]
    cal = {c["id"]: c for c in d["calibration_plan"]}
    assert "LOW LEVEL ONLY" in cal["CAL-P2-07"]["name"]
    assert not any("at power" in x for x in cal["CAL-P2-05"]["standards"] if "never" not in x)
    gate = next(s for s in seq if s["what"].startswith("GATE"))
    assert order.index(gate["step"]) == len(seq) - 2 and seq[-1]["what"].startswith("hot map")


def test_method_precedent_inference_labelled(d):
    e = next(x for x in d["published_method_precedents"] if x["id"] == "RF-SCHU24-05")
    assert e["use_here"].startswith("lane inference")


def test_plasma_power_keys_refused_anywhere(red, case):
    cal, rec = case
    for where, key in ((None, "P_RF_plasma_W"), (None, "plasma_power_W"), ("factors", "RF_power_to_plasma"),
                       ("settling", "p_plasma_kW"), ("temperatures_K", "plasma_W")):
        r = copy.deepcopy(rec)
        (r if where is None else r[where])[key] = 1.0
        _raises(red, red.ForwardAsPlasmaError, r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["power_labels"] = {"plasma_power": "P_net"}
    _raises(red, red.ForwardAsPlasmaError, r, {"SYN": cal})
    assert red.reduce_record(rec, {"SYN": cal})["plasma_state"]["mode"] == "UNLIT"   # plasma_state itself is fine


def test_evidence_tags_and_envelope_refuses_mixing(red, case):
    cal, rec = case
    assert red.reduce_record(rec, {"SYN": cal})["evidence_tag"] == red.TAG_NONE
    r_ar = copy.deepcopy(rec)
    r_ar["factors"]["gas"] = "Ar"
    o_ar = red.reduce_record(r_ar, {"SYN": cal})
    assert o_ar["evidence_tag"] == red.TAG_AR and "ENGINEERING_ONLY_NON_SCORING" in o_ar["evidence_tag"]
    r_n2 = copy.deepcopy(rec)
    r_n2["factors"]["gas"] = "N2"
    o_n2 = red.reduce_record(r_n2, {"SYN": cal})
    assert o_n2["evidence_tag"] == red.TAG_N2
    r_vi = copy.deepcopy(r_n2)
    r_vi["engineering_control"] = "OQ-VI-05"
    assert red.reduce_record(r_vi, {"SYN": cal})["evidence_tag"] == red.TAG_VI05
    r_bad = copy.deepcopy(rec)
    r_bad["engineering_control"] = "SOMETHING"
    _raises(red, red.RecordError, r_bad, {"SYN": cal})
    r_hot = _hot(rec, sig=0.01, mode="UNLIT", gas=None)
    _raises(red, red.RecordError, r_hot, {"SYN": cal})                  # HOT_MAP without a gas
    with pytest.raises(red.RecordError):
        red.mismatch_envelope([o_ar, o_n2], ["DUMMY_LOAD"])
    assert red.mismatch_envelope([o_ar], ["DUMMY_LOAD"])["evidence_tag"] == red.TAG_AR
    fake_measured = dict(o_n2, data_class="measured", evidence_status="measured (calibrated record reduction)")
    with pytest.raises(red.RecordError):
        red.mismatch_envelope([o_n2, fake_measured], ["DUMMY_LOAD"])


def test_nested_contract_in_schema_and_reducer(red, case):
    cal, rec = case
    sc = json.loads(OUT_SCHEMA.read_text(encoding="utf-8"))
    for k, fields in red.NESTED_REQUIRED.items():
        assert sc["properties"][k]["required"] == list(fields)
        assert set(sc["properties"][k]["properties"]) == set(fields)
    for k, sub in (("sweep", "direction"), ("plasma_state", "mode"), ("settling", "dwell_s"),
                   ("match_state", "auto_tune")):
        r = copy.deepcopy(rec)
        del r[k][sub]
        _raises(red, red.RecordError, r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["sweep"]["direction"] = "sideways"
    _raises(red, red.RecordError, r, {"SYN": cal})


# ------------------------------------------------------------------------------------------------ phase / plasma-state gate
TB = {"dark_background_record_id": "SYN-P1-DARK", "rf_powered_known_unlit_record_id": "SYN-P1-UNLIT",
      "known_lit_p1_record_id": "SYN-P1-LIT", "frozen_before_p2_map": True}


def _optical(r, sig, thr):
    r["plasma_state"].update({"optical_signal_V": sig, "unlit_threshold_V": thr,
                              "unlit_threshold_source": "SYNTHETIC P1 procedure id", "threshold_basis": dict(TB),
                              "photodiode_line_of_sight_ok": True, "photodiode_saturated": False,
                              "electrical_ignition_or_mode_transition": False, "electrical_indicator_basis": None})
    r["antenna_current"] = {"I_rms_A": 2.0, "probe_cal_id": "ACP"}
    r["factors"]["I_collector_A"] = 0.0
    return r


def _cold(rec, sig=0.01, thr=0.5):
    r = copy.deepcopy(rec)
    r["phase"] = "COLD_ANTENNA_POWERED_UNLIT"
    r["factors"].update({"gas": None, "mdot_icp_dedicated_mg_s": 0.0, "mdot_hall_anode_mg_s": 0.0,
                         "p_chamber_Pa": 1e-4})
    return _optical(r, sig, thr)


def _hot(rec, sig=2.0, thr=0.5, mode="H_MODE", gas="Ar"):
    r = copy.deepcopy(rec)
    r["phase"], r["p1_stable_region_ref"] = "HOT_MAP", "P1-REGION-SYN"
    r["factors"].update({"gas": gas, "p_chamber_Pa": 0.01})
    _optical(r, sig, thr)
    r["plasma_state"].update({"lit": mode != "UNLIT", "mode": mode})
    return r


def test_refuses_lit_plasma_in_non_hot_phase(red, case):
    cal, rec = case
    for ph in ("DUMMY_LOAD", "COLD_ANTENNA_POWERED_UNLIT"):
        for mode in ("H_MODE", "E_MODE", "UNCERTAIN"):
            r = _cold(rec) if ph == "COLD_ANTENNA_POWERED_UNLIT" else copy.deepcopy(rec)
            r["plasma_state"].update({"lit": True, "mode": mode})
            _raises(red, red.PlasmaStateError, r, {"SYN": cal})
            _raises(red, red.SequenceError, r, {"SYN": cal})          # PlasmaStateError is a SequenceError
    for lit, mode in ((False, "H_MODE"), (True, "UNLIT"), (None, "UNLIT")):   # inconsistent / unknown lit state
        r = copy.deepcopy(rec)
        r["plasma_state"].update({"lit": lit, "mode": mode})
        _raises(red, red.PlasmaStateError, r, {"SYN": cal})


def test_powered_unlit_requires_gas_off_and_optical_verification(red, case):
    cal, rec = case
    out = red.reduce_record(_cold(rec), {"SYN": cal})
    assert out["unlit_verification"]["verified_unlit"] is True
    for k, v in (("gas", "N2"), ("mdot_icp_dedicated_mg_s", 0.1), ("mdot_icp_dedicated_mg_s", None),
                 ("mdot_hall_anode_mg_s", None), ("p_chamber_Pa", None)):
        r = _cold(rec)
        r["factors"][k] = v
        _raises(red, red.PlasmaStateError, r, {"SYN": cal})
    for k, v in (("optical_signal_V", None), ("unlit_threshold_V", None), ("unlit_threshold_source", None),
                 ("unlit_threshold_source", "PENDING docs/experiments/hall_icp/p1_icp_bench/")):
        r = _cold(rec)
        r["plasma_state"][k] = v
        _raises(red, red.PlasmaStateError, r, {"SYN": cal})


def test_ignition_detected_abort_and_flag(red, case):
    cal, rec = case
    for sig in (0.5, 2.0):                                           # at or above the (record-carried) threshold
        _raises(red, red.IgnitionDetectedError, _cold(rec, sig=sig, thr=0.5), {"SYN": cal})


def test_cold_reference_only_from_verified_unlit(red, case):
    cal, rec = case
    cold_out = red.reduce_record(_cold(rec), {"SYN": cal})
    cr = red.cold_reference_from_reduced(cold_out, 300.0)
    assert cr["source_phase"] == "COLD_ANTENNA_POWERED_UNLIT" and cr["unlit_verification"]["verified_unlit"] is True
    assert cr["R_cold_ohm"] == pytest.approx(2.0, abs=1e-6) and cr["evidence_class"] == SYN
    dummy_out = red.reduce_record(rec, {"SYN": cal})
    with pytest.raises(red.PlasmaStateError):
        red.cold_reference_from_reduced(dummy_out, 300.0)            # not a powered-unlit record
    stripped = {k: v for k, v in cold_out.items() if k != "unlit_verification"}
    with pytest.raises(red.PlasmaStateError):
        red.cold_reference_from_reduced(stripped, 300.0)
    r = copy.deepcopy(rec)
    r["cold_reference_id"] = "CRX"
    c2 = copy.deepcopy(cal)
    c2["cold_references"]["CRX"] = cr
    assert red.reduce_record(r, {"SYN": c2})["resistance_split"]["R_cold_ohm"] == pytest.approx(2.0, abs=1e-6)
    bad = [dict(cr, source_phase="HOT_MAP"), dict(cr, unlit_verification=dict(cr["unlit_verification"],
                                                                                verified_unlit=False)),
           dict(cr, unlit_verification=dict(cr["unlit_verification"], optical_signal_V=0.9)),
           dict(cal["cold_references"]["CR1"], unlit_verification={})]
    for b in bad:
        c3 = copy.deepcopy(cal)
        c3["cold_references"]["CRX"] = b
        _raises(red, red.PlasmaStateError, r, {"SYN": c3})
    c4 = copy.deepcopy(cal)
    c4["cold_references"]["CRX"] = {k: v for k, v in cr.items() if k != "source_phase"}
    _raises(red, red.MissingCalibrationError, r, {"SYN": c4})


def test_rsplit_output_not_plasma_power(red, case):
    cal, rec = case
    r = copy.deepcopy(rec)
    r["cold_reference_id"] = "CR1"
    sp = red.reduce_record(r, {"SYN": cal})["resistance_split"]
    assert "P_delivered_x_Rsplit_fraction_W" in sp and "NOT P_plasma evidence" in sp["gate_use"]
    assert not any(red._is_plasma_power_key(k) for k in sp)


def test_mismatch_envelope_coverage_and_peak_sources(red, case):
    cal, rec = case
    full = red.reduce_record(rec, {"SYN": cal})
    r2 = copy.deepcopy(rec)
    r2["record_id"], r2["loss_method"] = "SYN-2", "declared_bound"
    bound = red.reduce_record(r2, {"SYN": cal})
    r3 = copy.deepcopy(rec)
    r3["record_id"], r3["methods"], r3["vi_probe"] = "SYN-3", ["deembed"], None
    derived = red.reduce_record(r3, {"SYN": cal})
    env = red.mismatch_envelope([full, bound, derived], ["DUMMY_LOAD"])
    cov = env["coverage"]
    assert cov["n_selected"] == 3 and cov["complete"] is False
    assert cov["P_delivered_W"]["n_included"] == 2 and set(cov["P_delivered_W"]["excluded"]) == {"SYN-2"}
    assert env["antenna_peaks_vi_measured"]["n_records"] == 2
    assert env["antenna_peaks_derived_from_P_delivered"]["n_records"] == 1
    assert "RP-CPL" in env["line_peaks_note"] and env["rating_status"] == "TBD_AFTER_IMPEDANCE_MAP"
    assert red.mismatch_envelope([full], ["DUMMY_LOAD"])["coverage"]["complete"] is True


def test_s08_powered_unlit_step_safety(d):
    s08 = next(s for s in d["hot_map_methodology"]["sequence"] if s["step"] == "S-08")
    assert any("P1 registered procedure" in p for p in s08["prerequisites"])
    for need in ("gas off", "base pressure", "INS-P2-10", "abort", "TBD - requires the P1 registered procedure"):
        assert need in s08["what"], need


# ------------------------------------------------------------------------------------------------ A9.4 P2Q-05 photodiode
A94 = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_4_p1_p2_owner_decisions.json"


def test_a94_pinned_and_state_classes(red, d):
    a94 = json.loads(A94.read_text(encoding="utf-8"))
    pins = {p["path"]: p["sha256"] for p in d["decision_pins"]}
    assert pins["docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json"] == \
        "b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d"
    assert pins["docs/decisions/OD_2026_09_30_A9_4_P1_P2_OWNER_DECISIONS.md"] == \
        "53cc026d63f85bd416f8ed8f4e8f9f7e7d7fc4429dccc45b86a51390b5c08b1c"
    assert list(red.MODE_LABELS) == a94["decisions"]["P2Q-05"]["state_classes"] == \
        ["UNLIT", "E_MODE", "H_MODE", "UNCERTAIN"]
    assert d["data_model"]["plasma_state_classes"] == list(red.MODE_LABELS)
    inc = d["a9_4_incorporation"]
    assert inc["follow_on"] == "fo_a9_4_incorporation" and inc["base_commit"] == \
        "875ed6d0a87202bc92706b28551b0e22eda2014d"
    assert inc["answered"]["P2Q-05"] == a94["decisions"]["P2Q-05"]["status"]


def test_a94_p2q05_answered_and_items(d):
    qs = {q["id"] for q in d["open_owner_questions"]}
    assert "P2Q-05" not in qs and "P2Q-09" in qs
    applied = [o for o in d["owner_answers_applied"] if isinstance(o["ref"], dict) and o["ref"].get("kind") == "A9.4"]
    by = {o["ref"]["decision"]: o for o in applied}
    assert by["P2Q-05"]["how"].startswith("ANSWERED") and "p1_needed_rfqs" in by
    assert by["P2Q-05"]["ref"]["path"] == "docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json"
    items = {it["id"]: it for it in d["items"]}
    assert items["HM-R14"]["status"] == "OWNER_GIVEN" and "UNCERTAIN" in items["HM-R14"]["value"]
    assert items["HM-R15"]["value"].startswith("TBD - requires") and items["HM-R15"]["evidence_class"] is None
    assert items["HM-F05"]["name"] == "plasma state / mode (UNLIT, E_MODE, H_MODE, UNCERTAIN)"
    ins = {i["id"]: i for i in d["instrument_list"]}
    assert ins["INS-P2-10"]["status"] == "OWNER_GIVEN" and "A9.4 P2Q-05" in ins["INS-P2-10"]["a9_3_rf_package_line"]
    specs = " ".join(x["quantity"] for x in ins["INS-P2-10"]["required_specs"])
    for need in ("amplifier", "DAQ channel", "line of sight"):
        assert need in specs, need
    assert "not purchase orders, advance payments" in ins["INS-P2-10"]["purchase"]
    seq = {x["step"]: x for x in d["hot_map_methodology"]["sequence"]}
    assert "HM-R15" in seq["S-10"]["what"] and any("HM-R15" in p_ for p_ in seq["S-08"]["prerequisites"])
    txt = json.dumps(d)
    assert "E_MODE" in txt and '"mode": "E"' not in txt


def test_a94_classify_plasma_state(red):
    base = {"optical_signal_V": 0.01, "unlit_threshold_V": 0.5, "threshold_basis": dict(TB),
            "photodiode_line_of_sight_ok": True, "photodiode_saturated": False,
            "electrical_ignition_or_mode_transition": False, "electrical_indicator_basis": None}
    assert red.classify_plasma_state(base)[0] == "UNLIT"
    assert red.classify_plasma_state(dict(base, electrical_ignition_or_mode_transition=True,
                                          electrical_indicator_basis="reflected-power step"))[0] == "UNCERTAIN"
    assert red.classify_plasma_state(dict(base, photodiode_line_of_sight_ok=False))[0] == "UNCERTAIN"
    assert red.classify_plasma_state(dict(base, photodiode_saturated=True))[0] == "UNCERTAIN"
    lit = dict(base, optical_signal_V=2.0)
    assert red.classify_plasma_state(dict(lit, lit_mode_assignment="E_MODE"))[0] == "E_MODE"
    assert red.classify_plasma_state(dict(lit, lit_mode_assignment="H_MODE"))[0] == "H_MODE"
    assert red.classify_plasma_state(lit)[0] == "UNCERTAIN"
    with pytest.raises(red.PlasmaStateError):                         # threshold without its A9.4 basis
        red.classify_plasma_state(dict(base, threshold_basis=None))
    with pytest.raises(red.PlasmaStateError):
        red.classify_plasma_state(dict(base, threshold_basis=dict(TB, frozen_before_p2_map=False)))
    with pytest.raises(red.PlasmaStateError):                         # no photodiode reading
        red.classify_plasma_state(dict(base, optical_signal_V=None))
    with pytest.raises(red.PlasmaStateError):                         # electrical evidence without its basis
        red.classify_plasma_state(dict(base, electrical_ignition_or_mode_transition=True))


def test_a94_powered_unlit_needs_optical_proof(red, case):
    cal, rec = case
    out = red.reduce_record(_cold(rec), {"SYN": cal})
    uv = out["unlit_verification"]
    assert uv["state_class"] == "UNLIT" and uv["threshold_basis"] == TB
    for k, v in (("photodiode_line_of_sight_ok", False), ("photodiode_saturated", True)):
        r = _cold(rec)
        r["plasma_state"][k] = v
        _raises(red, red.UncertainPlasmaStateError, r, {"SYN": cal})   # not automatically valid
    r = _cold(rec)
    r["plasma_state"].update({"electrical_ignition_or_mode_transition": True,
                              "electrical_indicator_basis": "antenna-current step"})
    _raises(red, red.UncertainPlasmaStateError, r, {"SYN": cal})       # UNCERTAIN, never forced to UNLIT
    for k in ("threshold_basis", "photodiode_line_of_sight_ok", "photodiode_saturated",
              "electrical_ignition_or_mode_transition"):
        r = _cold(rec)
        r["plasma_state"][k] = None
        _raises(red, red.PlasmaStateError, r, {"SYN": cal})
    r = _cold(rec)
    r["antenna_current"] = None                                        # corroboration recorded simultaneously
    _raises(red, red.PlasmaStateError, r, {"SYN": cal})
    r = _cold(rec)
    r["factors"]["I_collector_A"] = None
    _raises(red, red.PlasmaStateError, r, {"SYN": cal})
    cr = red.cold_reference_from_reduced(out, 300.0)
    bad = dict(out, unlit_verification=dict(uv, state_class="UNCERTAIN"))
    with pytest.raises(red.PlasmaStateError):
        red.cold_reference_from_reduced(bad, 300.0)
    c2 = copy.deepcopy(cal)
    c2["cold_references"]["CRU"] = dict(cr, unlit_verification=dict(cr["unlit_verification"], state_class="UNCERTAIN"))
    r = copy.deepcopy(rec)
    r["cold_reference_id"] = "CRU"
    _raises(red, red.PlasmaStateError, r, {"SYN": c2})


def test_a94_hot_map_classification_and_uncertain_refused(red, case):
    cal, rec = case
    out = red.reduce_record(_hot(rec, mode="H_MODE"), {"SYN": cal})
    assert out["plasma_state_classification"]["state_class"] == "H_MODE"
    assert red.reduce_record(_hot(rec, mode="E_MODE"), {"SYN": cal})["plasma_state_classification"]["state_class"] \
        == "E_MODE"
    assert red.reduce_record(_hot(rec, sig=0.01, mode="UNLIT"), {"SYN": cal})["plasma_state_classification"][
        "state_class"] == "UNLIT"
    _raises(red, red.UncertainPlasmaStateError, _hot(rec, mode="UNCERTAIN"), {"SYN": cal})   # never a map point
    r = _hot(rec, sig=0.01, mode="UNLIT")
    r["plasma_state"].update({"electrical_ignition_or_mode_transition": True,
                              "electrical_indicator_basis": "|Gamma| step at fixed tuning"})
    _raises(red, red.UncertainPlasmaStateError, r, {"SYN": cal})
    r = _hot(rec, mode="H_MODE")
    r["plasma_state"]["photodiode_saturated"] = True
    _raises(red, red.UncertainPlasmaStateError, r, {"SYN": cal})
    _raises(red, red.PlasmaStateError, _hot(rec, sig=0.01, mode="H_MODE"), {"SYN": cal})    # declared vs optical
    r = _hot(rec)
    r["antenna_current"] = None
    _raises(red, red.PlasmaStateError, r, {"SYN": cal})


# ------------------------------------------------------------------ A9.6 cross-lane integration (fo_a9_6_cross_lane_integration)
_XL_SELF = 'P2'
_XL_JSON = {
    "P1": "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
    "P2": "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
    "P3": "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json",
    "P4": "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
    "MP": "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json",
    "XE": "docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json",
    "RFQ": "docs/procurement/rfq_a9_v2/rfq_a9_v2.json",
}
_XL_MD = ['docs/experiments/hall_icp/p2_impedance_map/P2_IMPEDANCE_PREP.md']
_XL_BUILDER = 'docs/experiments/hall_icp/p2_impedance_map/build_p2_impedance_prep.py'
_XL_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def _xl_load(k):
    return __import__("json").loads((_XL_ROOT / _XL_JSON[k]).read_text(encoding="utf-8"))


def _xl_demands(d):
    ifd = d["interface_demands"]
    return [e for v in ifd.values() for e in v] if isinstance(ifd, dict) else list(ifd)


def _xl_builder():
    import importlib.util
    spec = importlib.util.spec_from_file_location("xl_builder_" + _XL_SELF.lower(), str(_XL_ROOT / _XL_BUILDER))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_xlane_pairs_reconciled_both_directions():
    """A9.6 sec. 5-6: every cross-lane interface demand of this package has exactly one matching entry in the
    counterpart package: same pair id, identical quantity / units / status text, mutual pointers; a single-pair entry
    carries the pair's units and status itself; no pair status is a PASS."""
    here = _xl_load(_XL_SELF)
    n = 0
    for e in _xl_demands(here):
        for x in e.get("xref", []):
            pkg, cid = x["counterpart"].split(":", 1)
            assert x["counterpart_path"] == _XL_JSON[pkg]
            there = _xl_demands(_xl_load(pkg))
            match = [(f, y) for f in there if f["id"] == cid for y in f.get("xref", []) if y["pair"] == x["pair"]]
            assert len(match) == 1, (x["pair"], x["counterpart"])
            f, y = match[0]
            assert y["counterpart"] == _XL_SELF + ":" + e["id"], x["pair"]
            for k in ("quantity", "units", "status"):
                assert y[k] == x[k], (x["pair"], k)
            assert not x["status"].upper().startswith("PASS"), x["pair"]
            if len(e["xref"]) == 1:
                assert e["units"] == x["units"] and e["status"] == x["status"], e["id"]
            n += 1
    assert n >= 1


def test_xlane_references_checked_not_pinned_not_stale():
    """A9.6 sec. 18 'no stale references': no 'PENDING <merged package>' marker survives; every merged package is
    recorded MERGED and never sha-pinned (packages read each other back: a pin would be circular); the builder's
    build-time id check passes on the committed JSON and refuses a broken counterpart id."""
    import copy
    import hashlib
    import re
    doc = _xl_load(_XL_SELF)
    txt = (_XL_ROOT / _XL_JSON[_XL_SELF]).read_text(encoding="utf-8") + "".join(
        (_XL_ROOT / p).read_text(encoding="utf-8") for p in _XL_MD)
    for k, p in _XL_JSON.items():
        if k == _XL_SELF:
            continue
        d = p.rsplit("/", 1)[0]
        assert re.search(r"PENDING[ :`'\"]*" + re.escape(d), txt) is None, d
        sha = hashlib.sha256((_XL_ROOT / p).read_bytes()).hexdigest()
        assert sha not in txt, "sha-pinned merged package " + p
    rec = doc["merged_cross_lane"]
    assert rec["build_order"] == ["P4", "XE", "P1", "P2", "P3", "MP", "RFQ"]
    for k, v in rec["packages"].items():
        assert v["state"] == "MERGED" and v["sha_pinned"] is False and v["path"] == _XL_JSON[k]
    b = _xl_builder()
    assert b.xlane_check(doc) == []
    bad = copy.deepcopy(doc)
    for e in _xl_demands(bad):
        if e.get("xref"):
            e["xref"][0]["counterpart"] = e["xref"][0]["counterpart"].split(":")[0] + ":NO-SUCH-ID"
            break
    assert b.xlane_check(bad)

