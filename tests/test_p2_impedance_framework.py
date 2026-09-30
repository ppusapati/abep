"""Tests for the P2 impedance-map FRAMEWORK (docs/experiments/hall_icp/p2_impedance_map/p2_framework.py; follow-on
fo_a9_6_p2_framework_completion, owner directive A9.6 sec. 9 and 14).

Checks, on SYNTHETIC (clearly labelled) data and closed forms: Touchstone 1.1 reading / writing and every refusal;
S-parameter storage and exact-frequency extraction; one-port SOL error terms and correction; coupler factors and the
published AN 1287-3 Fig. 14 worked example; V/I calibration on a known load; local-match state logging; de-embedding
from Touchstone-derived two-ports against closed-form cascades; delivered power refused while the line / match loss is
unverified; mixed synthetic / measured evidence refused; GUM linear vs analytic vs seeded Monte Carlo propagation;
E/H transition detection and hysteresis (criteria never defaulted); impedance-map writer / reader round trip and
tamper detection; OUT_OF_DOMAIN vs NOT_EVALUATED; rating structure never selects a rating; package section content.
Run: python -m pytest -q tests/test_p2_impedance_framework.py
"""
from __future__ import annotations

import cmath
import copy
import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "experiments" / "hall_icp" / "p2_impedance_map"
FW_PATH = LANE / "p2_framework.py"
OUT_JSON = LANE / "p2_impedance_prep_v1.json"
OUT_MD = LANE / "P2_IMPEDANCE_PREP.md"
MAP_SCHEMA = LANE / "p2_impedance_map_schema_v1.json"
SYN = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"
Z0 = 50.0
F0 = 13.56e6


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def fw():
    return _load("p2_framework_under_test", FW_PATH)


@pytest.fixture(scope="module")
def red(fw):
    return fw.RED                    # same module object the framework uses (exception identity)


@pytest.fixture(scope="module")
def d():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ synthetic fixtures
POS = {"C_series": "SYN-1", "C_shunt": "SYN-1"}
TS_MODEL = {"kind": "two_port", "tuning_state_id": "TS1", "Z_load_ohm": [Z0, 0.0],
            "Z_load_basis": "SYNTHETIC calorimetric reference load"}
LB_MODEL = {"kind": "declared_bound", "loss_bound_id": "LB1"}


SYN_LOSS_REGS = {"k": {"SYN-K-REG-01": {"value": 2.0, "source": "SYNTHETIC test registration"},
                        "SYN-K-REG-K1": {"value": 1.0, "source": "SYNTHETIC test registration"}},
                  "u_eta_pred": {"SYN-SPARAM-UNC-01": {"value": 0.01, "source": "SYNTHETIC S-parameter uncertainty"},
                                 "SYN-SPARAM-UNC-06": {"value": 0.06, "source": "SYNTHETIC S-parameter uncertainty"}}}
_K_IDS = {2.0: "SYN-K-REG-01", 1.0: "SYN-K-REG-K1"}
_U_IDS = {0.01: "SYN-SPARAM-UNC-01", 0.06: "SYN-SPARAM-UNC-06"}


def _verify(fw, red, cal, model_ref, vid, *, eta_meas=None, u_eta_pred=0.01, k=2.0, k_reg=None, **kw):
    """At-power loss verification produced by p2_framework.verify_line_match_loss (MET-07): P_ref_load is chosen so
    that eta_meas (default: the model's own prediction) is what the synthetic calorimeter 'measured'."""
    eta = red.loss_model_prediction(cal, model_ref)[0] if eta_meas is None else eta_meas
    args = dict(verification_id=vid, method="CAL-P2-09_calorimetric_at_power", cal=cal, model_ref=model_ref,
                u_eta_pred=u_eta_pred if model_ref["kind"] == "two_port" else 0.0, P_net_W=100.0, u_P_net_W=1.0,
                P_ref_load_W=100.0 * eta, u_P_ref_load_W=1.0, k=k,
                k_registration_id=k_reg if k_reg is not None else _K_IDS.get(k, "SYN-K-REG-01"),
                evidence_record_ids=["SYN-CALORIMETRY-01"], data_class=cal["data_class"],
                u_eta_pred_basis_id=_U_IDS.get(u_eta_pred, "SYN-SPARAM-UNC-01"))
    args.update(kw)
    return fw.verify_line_match_loss(**args)


def _c(z):
    return [z.real, z.imag]


def _line(theta_deg):
    th = math.radians(theta_deg)
    return (complex(math.cos(th)), 1j * Z0 * math.sin(th), 1j * math.sin(th) / Z0, complex(math.cos(th)))


ELEMENTS = [{"id": "C1", "kind": "series", "Z_ohm": [0.5, -80.0]},
            {"id": "C2", "kind": "shunt", "Z_ohm": [1.3888888888888888, -83.33333333333333]}]


def _s2p_text(fw, red, abcd, fmt="RI", unit="MHZ"):
    s11, s12, s21, s22 = red.abcd_to_s(abcd, Z0)
    return fw.write_touchstone(2, [{"f_Hz": 13.0e6, "S11": s11, "S21": s21, "S12": s12, "S22": s22},
                                   {"f_Hz": F0, "S11": s11, "S21": s21, "S12": s12, "S22": s22},
                                   {"f_Hz": 14.0e6, "S11": s11, "S21": s21, "S12": s12, "S22": s22}],
                               unit=unit, fmt=fmt, r_ohm=Z0, comment="SYNTHETIC")


def _cal_from_touchstone(fw, red, line_abcd, match_abcd, e=(complex(0.01, -0.02), complex(0.03, 0.01),
                                                             complex(0.98, 0.05)),
                         fix=(1 + 0j, complex(0.05, 3.0), 0j, 1 + 0j), data_class="synthetic_test"):
    lt = fw.parse_touchstone(_s2p_text(fw, red, line_abcd), 2)
    mt = fw.parse_touchstone(_s2p_text(fw, red, match_abcd, fmt="MA"), 2)
    ls = fw.sparam_set(lt, set_id="SYN-LINE", from_plane="RP-CPL", to_plane="RP-MIN", cal_id="SYN-2P",
                       phase_calibrated=True, data_class=data_class)
    ms = fw.sparam_set(mt, set_id="SYN-MATCH-TS1", from_plane="RP-MIN", to_plane="RP-ANT", cal_id="SYN-2P",
                       phase_calibrated=True, data_class=data_class, tuning_state_id="TS1", positions=POS)
    terms = {"e00": e[0], "e11": e[1], "e10e01": e[2]}
    lab = SYN if data_class == "synthetic_test" else "measured"
    cal = {"schema": red.CAL_SCHEMA_ID, "calibration_set_id": "SYN", "data_class": data_class, "f_Hz": F0,
            "Z0_ohm": Z0, "power_sensors": {"PS": {"CF_fwd": 1.0, "CF_ref": 1.0, "certificate": "SYNTHETIC"}},
            "coupler": fw.coupler_error_model(terms, "SYN-CPL"),
            "two_ports": {"line": fw.two_port_entry(ls, F0, Z0), "match_states": {"TS1": fw.two_port_entry(ms, F0, Z0)}},
            "vi_probe": {"cal_id": "VI", "phase_calibrated": True, "k_V": [1.0, 0.0], "k_I": [1.0, 0.0],
                         "fixture_abcd": [[_c(fix[0]), _c(fix[1])], [_c(fix[2]), _c(fix[3])]],
                         "fixture_from_plane": "RP-VI", "fixture_to_plane": "RP-ANT", "amplitude_convention": "peak"},
            "loss_bounds": {"LB1": {"loss_fraction_max": 0.1, "source": "SYNTHETIC", "evidence_class": "assumed",
                                    "verification": None}},
            "cold_references": {"CR1": {"R_cold_ohm": 1.5, "source_record_id": "SYN-COLD",
                                        "source_phase": "CAL-P2-08_VNA_UNPOWERED",
                                        "unlit_verification": {"basis": "SYNTHETIC CAL-P2-08 VNA record"},
                                        "evidence_class": lab, "antenna_temperature_K": 300.0}},
            "antenna_current_probe": {"cal_id": "ACP", "k_mag": 1.0, "certificate": "SYNTHETIC"},
            "loss_verification": None, "loss_check_registrations": copy.deepcopy(SYN_LOSS_REGS)}
    cal["loss_verification"] = _verify(fw, red, cal, TS_MODEL, "SYN-LV-01")
    cal["loss_bounds"]["LB1"]["verification"] = _verify(fw, red, cal, LB_MODEL, "SYN-LV-LB1")
    return cal


def _rec(fw, red, cal, z_ant, p_fwd=100.0, rid="SYN-1"):
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
    return {"schema": red.SCHEMA_ID, "record_id": rid, "data_class": cal["data_class"], "phase": "DUMMY_LOAD",
            "calibration_set_id": "SYN", "f_Hz": F0, "Z0_ohm": Z0,
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
                             "electrical_ignition_or_mode_transition": None, "electrical_indicator_basis": None,
                             "mode_indicator_basis": None},
            "sweep": {"sweep_id": "S", "direction": "single", "index": 0}, "settling": {"dwell_s": None, "settled": None},
            "temperatures_K": {}, "cold_reference_id": None, "p1_stable_region_ref": None, "antenna_current": None}


@pytest.fixture()
def case(fw, red):
    cal = _cal_from_touchstone(fw, red, _line(30.0), fw.ladder_abcd(ELEMENTS))
    return cal, _rec(fw, red, cal, complex(2.0, 80.0))


# ------------------------------------------------------------------------------------------------ Touchstone
SPEC_EX1 = "!1-port S-parameter file, single frequency point\n# MHz S MA R 50\n!freq magS11 angS11\n2.000 0.894 -12.136\n"
SPEC_EX8 = ("!2-port network, S-parameter and noise data\n# GHZ S MA R 50\n2 .95 -26 3.57 157 .04 76 .66 -14\n"
            "22 .60 -144 1.30 40 .14 40 .56 -85\n! NOISE PARAMETERS\n4 .7 .64 69 .38\n18 2.7 .46 -33 .40\n")


def test_touchstone_spec_examples(fw):
    t = fw.parse_touchstone(SPEC_EX1, 1)                               # REF-TOUCHSTONE11 p. 7 Example 1
    assert t["Z0_ohm"] == 50.0 and t["defaults_applied"] == [] and len(t["points"]) == 1
    assert t["points"][0]["f_Hz"] == pytest.approx(2.0e6)
    assert t["points"][0]["S11"] == pytest.approx(cmath.rect(0.894, math.radians(-12.136)))
    t8 = fw.parse_touchstone(SPEC_EX8, 2)                              # Example 8: noise block after the data
    assert len(t8["points"]) == 2 and len(t8["noise"]) == 2
    assert t8["points"][0]["S21"] == pytest.approx(cmath.rect(3.57, math.radians(157)))
    assert t8["points"][0]["S12"] == pytest.approx(cmath.rect(0.04, math.radians(76)))
    assert t8["noise"][1]["f_Hz"] == pytest.approx(18e9)


def test_touchstone_two_port_order_and_formats(fw):
    pt = {"f_Hz": F0, "S11": complex(0.1, 0.2), "S21": complex(0.7, -0.1), "S12": complex(0.01, 0.02),
          "S22": complex(-0.3, 0.05)}                                  # non-reciprocal: order is observable
    for fmt in ("RI", "MA", "DB"):
        for unit in ("HZ", "KHZ", "MHZ", "GHZ"):
            back = fw.parse_touchstone(fw.write_touchstone(2, [pt], unit=unit, fmt=fmt, r_ohm=50.0), 2)
            for k in ("S11", "S21", "S12", "S22"):
                assert back["points"][0][k] == pytest.approx(pt[k], abs=1e-12), (fmt, unit, k)
            assert back["points"][0]["f_Hz"] == pytest.approx(F0, rel=1e-15)
    line = "# MHZ S RI R 50\n13.56 0.1 0.2 0.7 -0.1 0.01 0.02 -0.3 0.05\n"
    p = fw.parse_touchstone(line, 2)["points"][0]
    assert p["S21"] == complex(0.7, -0.1) and p["S12"] == complex(0.01, 0.02)     # '21' precedes '12' (spec p. 6)


def test_touchstone_refusals_and_explicit_defaults(fw):
    with pytest.raises(fw.TouchstoneError):
        fw.parse_touchstone("#\n1 0.5 0\n", 1)                          # defaults never silent
    t = fw.parse_touchstone("#\n1 0.5 0\n", 1, allow_spec_defaults=True)
    assert t["defaults_applied"] == ["unit", "parameter", "format", "R"] and t["points"][0]["f_Hz"] == 1e9
    assert t["option"] == {"unit": "GHZ", "parameter": "S", "format": "MA", "R": 50.0}
    bad = ["1 0.5 0\n# MHZ S MA R 50\n",                                # data before the option line
           "# MHZ S MA R 50\n2 0.5 0\n1 0.5 0\n",                        # decreasing frequency
           "# MHZ S MA R 50\n1 0.5 0\n1 0.5 0\n",                        # repeated frequency
           "# MHZ S MA R 50\n1 0.5\n",                                   # wrong count
           "# MHZ Y MA R 50\n1 0.5 0\n",                                 # not S-parameters
           "# MHZ S MA MA R 50\n1 0.5 0\n",                              # duplicate option
           "# MHZ S MA R 50 X\n1 0.5 0\n",                               # unknown token
           "# MHZ S MA R -5\n1 0.5 0\n",                                 # non-positive R
           "# MHZ S MA R 50\n1 -0.5 0\n",                                # negative magnitude
           "# MHZ S MA R 50\n1 nan 0\n",                                 # non-finite
           "# MHZ S MA R 50\n1 0.5 0 °\n",                          # non-ASCII
           "! only comments\n"]
    for txt in bad:
        with pytest.raises(fw.TouchstoneError):
            fw.parse_touchstone(txt, 1)
    with pytest.raises(fw.TouchstoneError):
        fw.parse_touchstone("# MHZ S RI R 50\n1 0 0 1 0 1 0 0 0\n", 1)  # a 2-port line in a 1-port file
    with pytest.raises(fw.TouchstoneError):
        fw.parse_touchstone(SPEC_EX1, 3)
    t2 = fw.parse_touchstone("# MHZ S MA R 50\n1 0.5 0\n# GHZ S RI R 75\n2 0.4 0\n", 1)
    assert t2["ignored_option_lines"] == 1 and t2["Z0_ohm"] == 50.0 and t2["points"][1]["f_Hz"] == 2e6


def test_read_touchstone_files(fw, red, tmp_path):
    p = tmp_path / "syn_line.S2P"
    p.write_text(_s2p_text(fw, red, _line(30.0)), encoding="ascii")
    t = fw.read_touchstone(p)
    assert t["n_ports"] == 2 and len(t["source_sha256"]) == 64 and t["source"] == str(p)
    q = tmp_path / "syn.s1p"
    q.write_text(SPEC_EX1, encoding="ascii")
    assert fw.read_touchstone(q)["n_ports"] == 1
    r = tmp_path / "syn.txt"
    r.write_text(SPEC_EX1, encoding="ascii")
    with pytest.raises(fw.TouchstoneError):
        fw.read_touchstone(r)


# ------------------------------------------------------------------------------------------------ S-parameter storage
def test_sparam_set_and_exact_frequency(fw, red):
    t = fw.parse_touchstone(_s2p_text(fw, red, _line(30.0)), 2)
    s = fw.sparam_set(t, set_id="L", from_plane="RP-CPL", to_plane="RP-MIN", cal_id="C", phase_calibrated=True,
                      data_class="synthetic_test")
    json.dumps(s)                                                     # JSON-able storage
    e = fw.two_port_entry(s, F0, Z0)
    assert red.cx(e["S21"], "S21") == pytest.approx(cmath.exp(-1j * math.radians(30.0)))
    assert "positions" not in e
    with pytest.raises(fw.SParamError):
        fw.two_port_entry(s, 13.57e6, Z0)                               # no interpolation
    with pytest.raises(fw.SParamError):
        fw.two_port_entry(s, F0, 75.0)                                  # no silent renormalization
    for fp, tp in (("RP-MIN", "RP-CPL"), ("RP-CPL", "RP-CPL"), ("RP-XYZ", "RP-MIN")):
        with pytest.raises(fw.SParamError):
            fw.sparam_set(t, set_id="L", from_plane=fp, to_plane=tp, cal_id="C", phase_calibrated=True,
                          data_class="synthetic_test")
    with pytest.raises(fw.SParamError):                                 # tuning state without positions
        fw.sparam_set(t, set_id="M", from_plane="RP-MIN", to_plane="RP-ANT", cal_id="C", phase_calibrated=True,
                      data_class="synthetic_test", tuning_state_id="TS1")
    with pytest.raises(fw.SParamError):
        fw.sparam_set(t, set_id="L", from_plane="RP-CPL", to_plane="RP-MIN", cal_id="C", phase_calibrated="yes",
                      data_class="synthetic_test")
    one = fw.sparam_set(fw.parse_touchstone(SPEC_EX1, 1), set_id="ANT", from_plane="RP-ANT", to_plane=None,
                        cal_id="C", phase_calibrated=True, data_class="synthetic_test")
    assert fw.one_port_gamma(one, 2.0e6) == pytest.approx(cmath.rect(0.894, math.radians(-12.136)))
    with pytest.raises(fw.SParamError):
        fw.two_port_entry(one, 2.0e6, Z0)


def test_plane_chain(fw, red, case):
    cal, _ = case
    tp = cal["two_ports"]
    assert fw.check_plane_chain([tp["line"], tp["match_states"]["TS1"]], "RP-CPL", "RP-ANT")
    with pytest.raises(red.ReferencePlaneError):
        fw.check_plane_chain([tp["match_states"]["TS1"]], "RP-CPL", "RP-ANT")
    with pytest.raises(red.ReferencePlaneError):
        fw.check_plane_chain([tp["line"]], "RP-CPL", "RP-ANT")


# ------------------------------------------------------------------------------------------------ SOL
def _meas(g, e00, e11, e10e01):
    m = e00 + e10e01 * g / (1 - e11 * g)
    return [m.real, m.imag]


def test_sol_error_terms_ideal_and_data_based(fw):
    e = (complex(0.02, -0.01), complex(0.05, 0.03), complex(0.9, -0.2))
    for actual in ((-1, 1, 0), (cmath.rect(1, math.radians(170)), cmath.rect(0.99, math.radians(-5)),
                                complex(0.01, 0.005))):   # ideal, then offset short / open with a non-ideal load
        stds = [{"id": n, "gamma_actual": _c(complex(g)), "gamma_measured": _meas(complex(g), *e),
                 "definition_source": "SYNTHETIC kit definition"} for n, g in zip(("S", "O", "L"), actual)]
        t = fw.sol_error_terms(stds)
        assert t["e00"] == pytest.approx(e[0], abs=1e-12)
        assert t["e11"] == pytest.approx(e[1], abs=1e-12)
        assert t["e10e01"] == pytest.approx(e[2], abs=1e-12)
        g = complex(0.3, -0.4)
        assert fw.sol_correct(complex(*_meas(g, *e)), t) == pytest.approx(g)
    four = stds + [{"id": "X", "gamma_actual": [0.0, 0.5], "gamma_measured": _meas(0.5j, *e),
                    "definition_source": "SYNTHETIC"}]
    t4 = fw.sol_error_terms(four)
    assert t4["e10e01"] == pytest.approx(e[2], abs=1e-12) and max(t4["residual_abs"].values()) < 1e-12
    assert t4["solution"].startswith("least squares")


def test_sol_refusals(fw, red):
    e = (0j, 0j, 1 + 0j)
    good = [{"id": n, "gamma_actual": [g, 0.0], "gamma_measured": _meas(complex(g), *e), "definition_source": "S"}
            for n, g in (("S", -1.0), ("O", 1.0), ("L", 0.0))]
    with pytest.raises(fw.CalibrationSolveError):
        fw.sol_error_terms(good[:2])
    with pytest.raises(fw.CalibrationSolveError):
        fw.sol_error_terms([good[0], good[0], good[0]])                # not distinct
    with pytest.raises(fw.CalibrationSolveError):
        fw.sol_error_terms([dict(good[0], definition_source="")] + good[1:])
    with pytest.raises(fw.FrameworkError):
        fw.sol_error_terms([dict(good[0], gamma_actual=-1.0)] + good[1:])   # complex values must be [re, im]
    t = fw.sol_error_terms(good)
    assert fw.coupler_error_model(t, "C")["plane"] == "RP-CPL"
    with pytest.raises(red.ReferencePlaneError):
        fw.coupler_error_model(t, "C", plane="RP-ANT")


# ------------------------------------------------------------------------------------------------ coupler
def test_coupler_factors_and_published_example(fw):
    cf = fw.coupler_power_factor(40.0, 0.5, 0.98, "indicated_over_incident")
    assert cf == pytest.approx(10 ** 4.05 / 0.98)
    for bad in ((40.0, 0.5, 0.98, "other"), (-1.0, 0.5, 0.98, "indicated_over_incident"),
                (40.0, -0.1, 0.98, "indicated_over_incident"), (40.0, 0.5, 0.0, "indicated_over_incident")):
        with pytest.raises(fw.FrameworkError):
            fw.coupler_power_factor(*bad)
    # REF-AN1287-3 p. 12 Fig. 14 worked example (published numbers; code check only)
    assert fw.term_from_dB(47.0) == pytest.approx(0.0045, abs=5e-5)
    assert fw.term_from_dB(36.0) == pytest.approx(0.0158, abs=5e-5)
    assert fw.tracking_term_from_dB(0.019) == pytest.approx(0.0022, abs=5e-5)
    tot = fw.reflection_worst_case_error(0.158, fw.term_from_dB(47), fw.term_from_dB(36),
                                         fw.tracking_term_from_dB(0.019), S21S12_mag=0.891 ** 2,
                                         E_L=fw.term_from_dB(47))
    assert tot == pytest.approx(0.0088, abs=1e-4)


def test_scalar_gamma_bounds(fw):
    b = fw.scalar_gamma_bounds(0.2, 0.0, 0.0, 0.0)
    assert b["gamma_min"] == pytest.approx(0.2) and b["gamma_max"] == pytest.approx(0.2)
    ed, es, ert = 0.01, 0.02, 0.003
    b = fw.scalar_gamma_bounds(0.2, ed, es, ert)
    lo, hi = b["gamma_min"], b["gamma_max"]
    assert lo < 0.2 < hi
    assert 0.2 - lo == pytest.approx(fw.reflection_worst_case_error(lo, ed, es, ert), abs=1e-8)
    assert hi - 0.2 == pytest.approx(fw.reflection_worst_case_error(hi, ed, es, ert), abs=1e-8)
    assert fw.scalar_gamma_bounds(0.005, ed, es, ert)["gamma_min"] == 0.0
    assert fw.scalar_gamma_bounds(0.999, ed, es, ert)["upper_is_passive_limit"] is True
    with pytest.raises(fw.FrameworkError):
        fw.scalar_gamma_bounds(1.2, ed, es, ert)


# ------------------------------------------------------------------------------------------------ V/I probe
def test_vi_calibration_on_known_load(fw):
    kv_true, ki_true = cmath.rect(1200.0, math.radians(3.0)), cmath.rect(0.8, math.radians(-7.0))
    z_known = complex(50.0, 0.0)
    i_true = cmath.rect(2.0, math.radians(20.0))
    v_true = z_known * i_true
    cal = fw.vi_calibration_from_known_load(_c(v_true / kv_true), _c(i_true / ki_true), _c(z_known),
                                            0.5 * (v_true * i_true.conjugate()).real, "peak", "SYNTHETIC 50-ohm load")
    z_other = complex(2.0, 80.0)                                     # verification on another load
    i2 = cmath.rect(1.5, math.radians(-40.0))
    v2 = z_other * i2
    r = fw.vi_power_and_impedance(_c(v2 / kv_true), _c(i2 / ki_true), cal["k_V"], cal["k_I"], "peak")
    assert complex(*r["Z_ohm"]) == pytest.approx(z_other)
    assert r["P_W"] == pytest.approx(0.5 * (v2 * i2.conjugate()).real)
    assert fw.k_from_mag_phase(2.0, 90.0) == pytest.approx([0.0, 2.0], abs=1e-15)
    rms = fw.vi_calibration_from_known_load(_c(v_true), _c(i_true), _c(z_known), 100.0, "rms", "S")
    assert fw.vi_power_and_impedance(_c(v_true), _c(i_true), rms["k_V"], rms["k_I"], "rms")["P_W"] == \
        pytest.approx(100.0)
    for args in ((_c(v_true), _c(i_true), [0.0, 50.0], 1.0, "peak", "S"),     # R_known = 0
                 (_c(v_true), _c(i_true), _c(z_known), 1.0, "average", "S"),
                 (_c(v_true), _c(i_true), _c(z_known), 1.0, "peak", ""),
                 (_c(v_true), _c(i_true), _c(z_known), -1.0, "peak", "S")):
        with pytest.raises(fw.FrameworkError):
            fw.vi_calibration_from_known_load(*args)
    with pytest.raises(fw.FrameworkError):
        fw.k_from_mag_phase(0.0, 0.0)


# ------------------------------------------------------------------------------------------------ match / ladder
def test_ladder_stress_closed_form(fw, red):
    v_l, i_l = complex(100.0, 20.0), complex(1.0, -0.5)
    st = fw.ladder_element_stress(ELEMENTS, _c(v_l), _c(i_l))
    zs = complex(*ELEMENTS[0]["Z_ohm"])
    zp = complex(*ELEMENTS[1]["Z_ohm"])
    i_sh = v_l / zp                                                 # shunt next to the load sees V_load
    i_in = i_l + i_sh
    v_in = v_l + zs * i_in
    by = {e["id"]: e for e in st["elements"]}
    assert by["C2"]["V_mag"] == pytest.approx(abs(v_l)) and by["C2"]["I_mag"] == pytest.approx(abs(i_sh))
    assert by["C1"]["I_mag"] == pytest.approx(abs(i_in)) and by["C1"]["V_mag"] == pytest.approx(abs(zs * i_in))
    assert complex(*st["V_in"]) == pytest.approx(v_in) and complex(*st["I_in"]) == pytest.approx(i_in)
    a, b, c, dd = fw.ladder_abcd(ELEMENTS)                          # consistent with the ABCD cascade
    assert a * v_l + b * i_l == pytest.approx(v_in) and c * v_l + dd * i_l == pytest.approx(i_in)
    fp = fw.feedthrough_peaks_from_network(fw.ladder_abcd(ELEMENTS), _c(v_l), _c(i_l))
    assert fp["V"] == pytest.approx(v_in)
    with pytest.raises(fw.FrameworkError):
        fw.ladder_element_stress([], _c(v_l), _c(i_l))
    with pytest.raises(fw.FrameworkError):
        fw.ladder_element_stress([{"id": "X", "kind": "diagonal", "Z_ohm": [1, 1]}], _c(v_l), _c(i_l))


def test_match_positions_logged_and_checked(fw, red, case):
    cal, rec = case
    assert red.reduce_record(rec, {"SYN": cal})["Z_antenna"]["deembed"]["R_ohm"] == pytest.approx(2.0, abs=1e-6)
    r = copy.deepcopy(rec)
    r["match_state"]["positions"] = {"C_series": "SYN-2", "C_shunt": "SYN-1"}     # a different setting
    with pytest.raises(red.RecordError):
        red.reduce_record(r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["match_state"]["positions"] = {}
    with pytest.raises(red.RecordError):
        red.reduce_record(r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["match_state"]["auto_tune"] = None
    with pytest.raises(red.RecordError):
        red.reduce_record(r, {"SYN": cal})
    c2 = copy.deepcopy(cal)
    del c2["two_ports"]["match_states"]["TS1"]["positions"]
    with pytest.raises(red.MissingCalibrationError):
        red.reduce_record(rec, {"SYN": c2})


# ------------------------------------------------------------------------------------------------ de-embedding
def test_deembed_from_touchstone_matches_closed_form(fw, red, case):
    cal, rec = case
    out = red.reduce_record(rec, {"SYN": cal})
    for m in ("vi_probe", "deembed"):
        assert out["Z_antenna"][m]["R_ohm"] == pytest.approx(2.0, abs=1e-6)
        assert out["Z_antenna"][m]["X_ohm"] == pytest.approx(80.0, abs=1e-6)
    z_ant = complex(2.0, 80.0)                                       # independent closed form of the cascade
    zm = 1 / (1 / z_ant + 1 / complex(*ELEMENTS[1]["Z_ohm"])) + complex(*ELEMENTS[0]["Z_ohm"])
    t = math.tan(math.radians(30.0))
    z_in = Z0 * (zm + 1j * Z0 * t) / (Z0 + 1j * zm * t)
    tp = cal["two_ports"]
    net = red.cascade(red.s_to_abcd(*[red.cx(tp["line"][k], k) for k in ("S11", "S12", "S21", "S22")], Z0),
                      red.s_to_abcd(*[red.cx(tp["match_states"]["TS1"][k], k) for k in ("S11", "S12", "S21", "S22")],
                                    Z0))
    assert red.z_in(net, z_ant) == pytest.approx(z_in)
    assert red.deembed_load(net, z_in) == pytest.approx(z_ant)
    g = complex(*out["at_RP_CPL"]["gamma_complex"])
    assert red.z_from_gamma(g, Z0) == pytest.approx(z_in, rel=1e-6)


# ------------------------------------------------------------------------------------------------ loss / P_delivered
def test_delivered_power_refused_when_loss_unverified(fw, red, case):
    cal, rec = case
    ok = red.reduce_record(rec, {"SYN": cal})
    assert isinstance(ok["P_delivered_W"], float) and ok["loss_status"].startswith("VERIFIED")
    LV = cal["loss_verification"]
    assert LV["status"] == red.LOSS_VERIFIED
    variants = [None, dict(LV, status="LOSS_MODEL_INCONSISTENT"), dict(LV, status="NOT_EVALUATED"),
                dict(LV, tuning_states=["TS-OTHER"]), dict(LV, method="datasheet"), dict(LV, evidence_record_ids=[]),
                {k: v for k, v in LV.items() if k != "method"}]
    for v in variants:
        c2 = copy.deepcopy(cal)
        c2["loss_verification"] = v
        out = red.reduce_record(rec, {"SYN": c2})
        assert out["loss_status"] == "UNVERIFIED"
        assert isinstance(out["P_delivered_W"], str) and out["P_delivered_W"].startswith("REFUSED")
        assert isinstance(out["P_line_match_loss_W"], str) and "match_line_efficiency" not in out
        assert out["Z_antenna"]["deembed"]["R_ohm"] == pytest.approx(2.0, abs=1e-6)   # impedance still reduced
        env = red.mismatch_envelope([out], ["DUMMY_LOAD"])
        assert env["coverage"]["complete"] is False
        assert "UNVERIFIED" in env["coverage"]["P_delivered_W"]["excluded"]["SYN-1"]
    c3 = copy.deepcopy(cal)
    del c3["loss_verification"]
    with pytest.raises(red.MissingCalibrationError):
        red.reduce_record(rec, {"SYN": c3})
    r = copy.deepcopy(rec)                                           # declared bound: verification required too
    r["loss_method"] = "declared_bound"
    assert isinstance(red.reduce_record(r, {"SYN": cal})["P_delivered_W"], dict)
    c4 = copy.deepcopy(cal)
    c4["loss_bounds"]["LB1"]["verification"] = None
    assert red.reduce_record(r, {"SYN": c4})["P_delivered_W"].startswith("REFUSED")
    c5 = copy.deepcopy(cal)
    del c5["loss_bounds"]["LB1"]["verification"]
    with pytest.raises(red.MissingCalibrationError):
        red.reduce_record(r, {"SYN": c5})


def test_verify_line_match_loss(fw, red, case):
    cal, rec = case
    eta = red.loss_model_prediction(cal, TS_MODEL)[0]
    v = _verify(fw, red, cal, TS_MODEL, "V1", eta_meas=eta - 0.005)
    assert v["status"] == red.LOSS_VERIFIED and v["normalized_statistic"] < 2.0
    assert v["eta_predicted"] == pytest.approx(eta) and v["model_ref"]["calibration_set_id"] == "SYN"
    assert red.loss_verification_status(v, cal, tuning_state_id="TS1") == (True, "")
    v2 = _verify(fw, red, cal, TS_MODEL, "V2", eta_meas=eta - 0.1)
    assert v2["status"] == fw.LOSS_INCONSISTENT
    assert red.loss_verification_status(v2, cal, tuning_state_id="TS1")[0] is False
    v3 = _verify(fw, red, cal, TS_MODEL, "V3", u_eta_pred=None)
    assert v3["status"] == fw.NOT_EVALUATED                          # missing uncertainty -> never verified
    with pytest.raises(fw.CriteriaMissingError):
        _verify(fw, red, cal, TS_MODEL, "V4", k=None)
    for bad in (None, "", "PENDING-LOCK-2", "TBD_OWNER"):         # k needs a registered k_registration_id (MET-07)
        with pytest.raises(fw.CriteriaMissingError):
            _verify(fw, red, cal, TS_MODEL, "V5", k_registration_id=bad)
    with pytest.raises(fw.FrameworkError):
        _verify(fw, red, cal, TS_MODEL, "V6", method="guess")
    with pytest.raises(fw.FrameworkError):                            # eta_pred must be the model's prediction
        _verify(fw, red, cal, TS_MODEL, "V7", eta_pred=0.5)
    with pytest.raises(fw.FrameworkError):
        _verify(fw, red, cal, TS_MODEL, "V8", evidence_record_ids=["PENDING-CAL"])
    with pytest.raises(fw.FrameworkError):                            # unknown tuning state
        _verify(fw, red, cal, dict(TS_MODEL, tuning_state_id="TS9"), "V9", eta_meas=0.6)
    # declared bound: one-sided (measured loss not above the bound beyond k u_c)
    vb = _verify(fw, red, cal, LB_MODEL, "VB1", eta_meas=0.95)
    assert vb["status"] == red.LOSS_VERIFIED and vb["eta_predicted"] == pytest.approx(0.9)
    assert red.loss_verification_status(vb, cal, loss_bound_id="LB1") == (True, "")
    vb2 = _verify(fw, red, cal, LB_MODEL, "VB2", eta_meas=0.8)
    assert vb2["status"] == fw.LOSS_INCONSISTENT
    assert red.loss_verification_status(vb, cal, loss_bound_id="LB2")[0] is False   # other bound
    assert red.loss_verification_status(vb, cal, tuning_state_id="TS1")[0] is False  # not a two-port check


def test_loss_verification_tied_to_model_met07(fw, red, case):
    """MET-07: a LOSS_MODEL_VERIFIED label alone never reconstructs P_delivered; the reducer recomputes the statistic,
    requires a registered k and ties eta_predicted to the two-port network / load of the check it verifies."""
    cal, rec = case
    lv = cal["loss_verification"]
    ok = red.reduce_record(rec, {"SYN": cal})
    assert ok["loss_status"] == "VERIFIED (SYN-LV-01)"

    def refused(v, c=None):
        c2 = copy.deepcopy(cal if c is None else c)
        c2["loss_verification"] = v
        out = red.reduce_record(rec, {"SYN": c2})
        assert out["loss_status"] == "UNVERIFIED", out["loss_status"]
        assert out["P_delivered_W"].startswith("REFUSED") and "match_line_efficiency" not in out
        return out["P_line_match_loss_W"]

    bare = {k: lv[k] for k in ("verification_id", "status", "method", "evidence_record_ids", "tuning_states",
                               "data_class")}
    assert "lacks" in refused(bare)                                   # status label alone (finding case 1)
    for f in ("k", "k_registration_id", "eta_measured", "u_eta_measured", "eta_predicted", "u_eta_predicted",
              "normalized_statistic", "model_ref", "comparison"):
        refused({k: v for k, v in lv.items() if k != f})
    for bad in ("", "PENDING-LOCK-2", "TBD"):
        assert "k registration" in refused(dict(lv, k_registration_id=bad))
    refused(dict(lv, k=0.0))
    # at-power check measured eta 0.5 while the network predicts ~0.61: a forged VERIFIED label with the true
    # statistic is refused (finding case 2), and so is a forged eta_predicted / statistic pair
    pr5 = 0.5 * lv["P_net_W"]                                         # forged label with consistent evidence
    um5 = 0.5 * math.hypot(lv["u_P_ref_load_W"] / pr5, lv["u_P_net_W"] / lv["P_net_W"])
    stat = red.loss_statistic("two_sided", 0.5, um5, lv["eta_predicted"], lv["u_eta_predicted"])
    assert "> k" in refused(dict(lv, P_ref_load_W=pr5, eta_measured=0.5, u_eta_measured=um5, normalized_statistic=stat))
    assert "recomputed" in refused(dict(lv, eta_measured=0.5))
    s2 = red.loss_statistic("two_sided", 0.5, lv["u_eta_measured"], 0.5, lv["u_eta_predicted"])
    s2 = red.loss_statistic("two_sided", 0.5, um5, 0.5, lv["u_eta_predicted"])
    assert "prediction" in refused(dict(lv, P_ref_load_W=pr5, eta_measured=0.5, u_eta_measured=um5, eta_predicted=0.5,
                                        normalized_statistic=s2))
    # the check verified another load / another network / another calibration set / another comparison
    mr = lv["model_ref"]
    assert "prediction" in refused(dict(lv, model_ref=dict(mr, Z_load_ohm=[5.0, 30.0])))
    c_other = copy.deepcopy(cal)
    c_other["two_ports"]["match_states"]["TS1"]["S21"] = [0.5, 0.1]
    assert "different two-port network" in refused(lv, c_other)
    assert "calibration set" in refused(dict(lv, model_ref=dict(mr, calibration_set_id="OTHER")))
    assert "comparison" in refused(dict(lv, comparison="one_sided_bound"))
    refused(dict(lv, model_ref=dict(mr, tuning_state_id="TS2")))
    # list form: one record per tuning state; none / ambiguous -> refused, never chosen silently
    assert red.reduce_record(rec, {"SYN": dict(cal, loss_verification=[lv])})["loss_status"].startswith("VERIFIED")
    assert "no loss verification names" in refused([dict(lv, model_ref=dict(mr, tuning_state_id="TS2"))])
    assert "ambiguous" in refused([lv, dict(lv, verification_id="SYN-LV-02")])
    # declared bound: the bound's verification must name that bound and its 1 - loss_fraction_max
    r = copy.deepcopy(rec)
    r["loss_method"] = "declared_bound"
    assert isinstance(red.reduce_record(r, {"SYN": cal})["P_delivered_W"], dict)
    c3 = copy.deepcopy(cal)
    c3["loss_bounds"]["LB1"]["loss_fraction_max"] = 0.05             # bound tightened after the check
    assert red.reduce_record(r, {"SYN": c3})["loss_status"] == "UNVERIFIED"
    c4 = copy.deepcopy(cal)
    c4["loss_bounds"]["LB1"]["verification"] = lv                    # a two-port check is not a bound check
    assert red.reduce_record(r, {"SYN": c4})["loss_status"] == "UNVERIFIED"
    # JSON round trip keeps the verification valid (no rounding in the record)
    cj = json.loads(json.dumps(cal))
    assert red.reduce_record(rec, {"SYN": cj})["loss_status"] == "VERIFIED (SYN-LV-01)"


def test_dissipated_fraction_matched(fw):
    a = 0.8
    assert fw.dissipated_fraction_matched(0j, a) == pytest.approx(1 - a * a)
    assert fw.dissipated_fraction_matched(0j, 1.0) == 0.0
    with pytest.raises(fw.FrameworkError):
        fw.dissipated_fraction_matched(0.5, 1.0)                    # active / inconsistent


def test_mixed_evidence_refused(fw, red, case):
    cal, rec = case
    r = copy.deepcopy(rec)
    r["data_class"] = "measured"
    with pytest.raises(red.MixedEvidenceError):
        red.reduce_record(r, {"SYN": cal})
    c2 = copy.deepcopy(cal)
    c2["loss_verification"] = dict(cal["loss_verification"], data_class="measured")
    with pytest.raises(red.MixedEvidenceError):
        red.reduce_record(rec, {"SYN": c2})
    c3 = copy.deepcopy(cal)
    c3["cold_references"]["CR1"]["evidence_class"] = "measured"
    r = copy.deepcopy(rec)
    r["cold_reference_id"] = "CR1"
    with pytest.raises(red.MixedEvidenceError):
        red.reduce_record(r, {"SYN": c3})
    mcal = _cal_from_touchstone(fw, red, _line(30.0), fw.ladder_abcd(ELEMENTS), data_class="measured")
    mrec = _rec(fw, red, mcal, complex(2.0, 80.0))                  # code-path check only: fabricated 'measured'
    assert red.reduce_record(mrec, {"SYN": mcal})["evidence_status"].startswith("measured")
    assert issubclass(red.MixedEvidenceError, red.RecordError)


# ------------------------------------------------------------------------------------------------ uncertainty
def test_gamma_uncertainty_analytic_linear_mc(fw):
    a = fw.gamma_vswr_pnet_uncertainty(100.0, 1.0, 4.0, 0.2, 0.5)
    cov = [[1.0, 0.5 * 1.0 * 0.2], [0.5 * 1.0 * 0.2, 0.04]]
    lin = fw.propagate_linear(lambda x: [math.sqrt(x[1] / x[0]), x[0] - x[1]], [100.0, 4.0], cov)
    assert lin["u_y"][0] == pytest.approx(a["u_gamma_mag"], rel=1e-7)
    assert lin["u_y"][1] == pytest.approx(a["u_P_net_W"], rel=1e-9)
    assert a["u_VSWR"] == pytest.approx(2 / (1 - a["gamma_mag"]) ** 2 * a["u_gamma_mag"])
    mc1 = fw.propagate_mc(lambda x: [math.sqrt(x[1] / x[0])], [100.0, 4.0], cov, n_trials=20000, seed=7)
    mc2 = fw.propagate_mc(lambda x: [math.sqrt(x[1] / x[0])], [100.0, 4.0], cov, n_trials=20000, seed=7)
    assert mc1 == mc2                                               # deterministic
    assert mc1["u_y"][0] == pytest.approx(a["u_gamma_mag"], rel=0.05)
    lo, hi = mc1["coverage_interval_95"][0]
    assert lo < a["gamma_mag"] < hi
    assert (hi - lo) / 2 == pytest.approx(1.96 * a["u_gamma_mag"], rel=0.08)
    with pytest.raises(fw.UncertaintyMissingError):
        fw.gamma_vswr_pnet_uncertainty(100.0, 1.0, 4.0, 0.2, None)   # correlation never defaulted
    with pytest.raises(fw.UncertaintyMissingError):
        fw.propagate_linear(lambda x: x, [1.0], None)
    with pytest.raises(fw.UncertaintyMissingError):
        fw.propagate_linear(lambda x: x, [1.0, 2.0], [[1.0, None], [None, 1.0]])
    with pytest.raises(fw.UncertaintyMissingError):
        fw.propagate_mc(lambda x: x, [1.0, 2.0], [[1.0, 2.0], [2.0, 1.0]], n_trials=1000, seed=1)   # not PSD
    with pytest.raises(fw.FrameworkError):
        fw.propagate_mc(lambda x: x, [1.0], [[1.0]], n_trials=10, seed=1)


def test_mc_coverage_interval_rule(fw):
    """JCGM 101 7.7.2 on a known case: identity model, Gaussian input -> interval ~ x +/- 1.96 u."""
    r = fw.propagate_mc(lambda x: [x[0]], [10.0], [[4.0]], n_trials=40000, seed=11)
    lo, hi = r["coverage_interval_95"][0]
    assert lo == pytest.approx(10 - 1.96 * 2, abs=0.08) and hi == pytest.approx(10 + 1.96 * 2, abs=0.08)
    assert r["y_mean"][0] == pytest.approx(10.0, abs=0.05)


def test_z_uncertainty_holomorphic_and_deembed(fw, red, case):
    g = complex(0.3, -0.2)
    ug = [[1e-4, 2e-5], [2e-5, 4e-4]]
    a = fw.z_from_gamma_uncertainty(g, ug, Z0)
    lin = fw.propagate_linear(lambda x: [c for c in _c(Z0 * (1 + complex(x[0], x[1])) / (1 - complex(x[0], x[1])))],
                              [g.real, g.imag], ug)
    for i in range(2):
        for k in range(2):
            assert a["U_Z_ohm2"][i][k] == pytest.approx(lin["U_y"][i][k], rel=1e-6)
    cal, rec = case
    tp = cal["two_ports"]
    x = (rec["coupler"]["reflection_raw"] + cal["coupler"]["e00"] + cal["coupler"]["e11"] + cal["coupler"]["e10e01"]
         + sum((tp["line"][k] for k in ("S11", "S12", "S21", "S22")), [])
         + sum((tp["match_states"]["TS1"][k] for k in ("S11", "S12", "S21", "S22")), []))
    f = fw.z_deembed_function(Z0)
    assert f(x) == pytest.approx([2.0, 80.0], abs=1e-6)
    n = len(x)
    u = [[(1e-4) ** 2 if i == k else 0.0 for k in range(n)] for i in range(n)]
    lin = fw.propagate_linear(f, x, u)
    mc = fw.propagate_mc(f, x, u, n_trials=3000, seed=3)
    assert lin["u_y"][0] > 0 and mc["u_y"][0] == pytest.approx(lin["u_y"][0], rel=0.1)
    pd = fw.p_delivered_uncertainty(90.0, 1.0, 0.8, 0.01)
    assert pd["u_P_delivered_W"] == pytest.approx(math.hypot(0.8 * 1.0, 90.0 * 0.01))
    with pytest.raises(fw.UncertaintyMissingError):
        fw.p_delivered_uncertainty(90.0, None, 0.8, 0.01)


# ------------------------------------------------------------------------------------------------ E/H transitions
CRIT = {"form": "absolute_step", "basis": "SYNTHETIC criteria", "frozen_before_p2_map": True,
        "step_photodiode_V": 0.5, "step_P_reflected_W": 2.0, "step_I_ant_rms_A": 0.5}


def _sweep(direction, rows, ts=("TS1",) * 10, valid=(True,) * 10):
    return [{"index": i, "direction": direction, "photodiode_valid": valid[i], "tuning_state_id": ts[i],
             "photodiode_V": pdv, "P_reflected_W": prf, "I_ant_rms_A": ia, "P_forward_W": pf, "P_delivered_W": pdl}
            for i, (pdv, prf, ia, pf, pdl) in enumerate(rows)]


UP = [(0.1, 1.0, 3.0, 50.0, 40.0), (0.2, 1.1, 3.1, 60.0, 48.0), (2.0, 6.0, 2.0, 70.0, 60.0), (2.1, 6.1, 2.0, 80.0, 70.0)]
DOWN = [(2.1, 6.1, 2.0, 80.0, 70.0), (2.0, 6.0, 2.0, 60.0, 52.0), (0.2, 1.1, 3.1, 50.0, 40.0),
        (0.1, 1.0, 3.0, 40.0, 32.0)]


def test_eh_detection_classes(fw):
    ev = fw.detect_eh_transitions(_sweep("up", UP), CRIT)["events"]
    assert [e["class"] for e in ev] == ["TRANSITION_CANDIDATE_CORROBORATED"] and ev[0]["emission_step"] == "UP"
    assert set(ev[0]["electrical_jumps"]) == {"P_reflected_W", "I_ant_rms_A"}
    opt = [(0.1, 1.0, 3.0, 50.0, None), (2.0, 1.1, 3.1, 60.0, None)]
    assert fw.detect_eh_transitions(_sweep("up", opt), CRIT)["events"][0]["class"] == \
        "TRANSITION_CANDIDATE_OPTICAL_ONLY"
    ele = [(0.1, 1.0, 3.0, 50.0, None), (0.2, 6.0, 3.1, 60.0, None)]
    assert fw.detect_eh_transitions(_sweep("up", ele), CRIT)["events"][0]["class"] == "UNCERTAIN_ELECTRICAL_ONLY"
    inv = fw.detect_eh_transitions(_sweep("up", ele, valid=(True, False)), CRIT)["events"]
    assert inv[0]["class"] == "UNCERTAIN_PHOTODIODE_INVALID"
    ts = fw.detect_eh_transitions(_sweep("up", UP, ts=("TS1", "TS1", "TS2", "TS2")), CRIT)["events"][0]
    assert ts["reflected_evaluable"] is False and ts["electrical_jumps"] == ["I_ant_rms_A"]   # tuning changed


def test_eh_criteria_never_defaulted(fw):
    sw = _sweep("up", UP)
    with pytest.raises(fw.CriteriaMissingError):
        fw.detect_eh_transitions(sw, None)
    for bad in (dict(CRIT, frozen_before_p2_map=False), dict(CRIT, basis="TBD"), dict(CRIT, form="guess"),
                {k: v for k, v in CRIT.items() if k != "step_I_ant_rms_A"},
                {"form": "k_times_uc", "basis": "S", "frozen_before_p2_map": True}):
        with pytest.raises(fw.CriteriaMissingError):
            fw.detect_eh_transitions(sw, bad)
    k_crit = {"form": "k_times_uc", "basis": "SYNTHETIC", "frozen_before_p2_map": True, "k": 3.0}
    with pytest.raises(fw.UncertaintyMissingError):
        fw.detect_eh_transitions(sw, k_crit)                        # step uncertainties missing
    for p in sw:
        p.update({"u_photodiode_V": 0.05, "u_P_reflected_W": 0.2, "u_I_ant_rms_A": 0.05})
    assert fw.detect_eh_transitions(sw, k_crit)["events"][0]["class"] == "TRANSITION_CANDIDATE_CORROBORATED"
    with pytest.raises(fw.FrameworkError):
        fw.detect_eh_transitions(_sweep("up", UP[:1]), CRIT)
    mixed = _sweep("up", UP)
    mixed[1]["direction"] = "down"
    with pytest.raises(fw.FrameworkError):
        fw.detect_eh_transitions(mixed, CRIT)
    rev = _sweep("up", UP)[::-1]
    with pytest.raises(fw.FrameworkError):
        fw.detect_eh_transitions(rev, CRIT)


def test_hysteresis_reported_not_judged(fw):
    fx = {"mdot": "SYN", "p": "SYN"}
    h = fw.hysteresis(_sweep("up", UP), _sweep("down", DOWN), CRIT, fx, dict(fx))
    assert h["judgement"].startswith("REPORTED_NOT_JUDGED")
    w = h["width_P_forward_W"]
    assert w["up_interval"] == [60.0, 70.0] and w["down_interval"] == [50.0, 60.0]
    assert w["width_min"] == 0.0 and w["width_max"] == 20.0
    assert h["width_P_delivered_W"]["up_interval"] == [48.0, 60.0]
    down_nopd = [r[:4] + ("REFUSED - loss unverified",) for r in DOWN]
    h2 = fw.hysteresis(_sweep("up", UP), _sweep("down", down_nopd), CRIT, fx, dict(fx))
    assert h2["width_P_delivered_W"].startswith("NOT_EVALUATED") and isinstance(h2["width_P_forward_W"], dict)
    with pytest.raises(fw.FrameworkError):
        fw.hysteresis(_sweep("up", UP), _sweep("down", DOWN), CRIT, fx, {"mdot": "OTHER"})
    with pytest.raises(fw.FrameworkError):
        fw.hysteresis(_sweep("down", DOWN), _sweep("up", UP), CRIT, fx, dict(fx))
    none = fw.hysteresis(_sweep("up", UP[:2]), _sweep("down", DOWN[:2]), CRIT, fx, dict(fx))
    assert none["width_P_forward_W"].startswith("NOT_EVALUATED")


# ------------------------------------------------------------------------------------------------ map storage
TB = {"dark_background_record_id": "SYN-P1-DARK", "rf_powered_known_unlit_record_id": "SYN-P1-UNLIT",
      "known_lit_p1_record_id": "SYN-P1-LIT", "frozen_before_p2_map": True}


def _hot(rec, mode="H_MODE", sig=2.0, gas="Ar", rid="SYN-H"):
    r = copy.deepcopy(rec)
    r["record_id"], r["phase"], r["p1_stable_region_ref"] = rid, "HOT_MAP", "P1-REGION-SYN"
    r["factors"].update({"gas": gas, "p_chamber_Pa": 0.01, "I_collector_A": 0.0, "P_RF_setpoint_W": 100.0,
                         "mdot_hall_anode_mg_s": 0.0})
    r["plasma_state"].update({"lit": mode != "UNLIT", "mode": mode, "optical_signal_V": sig, "unlit_threshold_V": 0.5,
                              "unlit_threshold_source": "SYNTHETIC P1 procedure id", "threshold_basis": dict(TB),
                              "photodiode_line_of_sight_ok": True, "photodiode_saturated": False,
                              "electrical_ignition_or_mode_transition": False, "electrical_indicator_basis": None,
                              "mode_indicator_basis": ("SYNTH HM-R06 indicators" if mode in ("E_MODE", "H_MODE")
                                                       else None)})
    r["antenna_current"] = {"I_rms_A": 2.0, "probe_cal_id": "ACP"}
    return r


def test_ingest_preserves_excluded_and_uncertain(fw, red, case):
    cal, rec = case
    recs = [_hot(rec, rid="H1"), _hot(rec, mode="UNCERTAIN", rid="H2"), dict(copy.deepcopy(rec), record_id="D2",
                                                                              data_class="measured"),
            _hot(rec, rid="H3", gas="N2")]
    red_ok, excl = fw.ingest_records(recs, {"SYN": cal})
    assert [r["record_id"] for r in red_ok] == ["H1", "H3"]
    by = {e["record_id"]: e for e in excl}
    assert by["H2"]["refusal_class"] == "UncertainPlasmaStateError" and by["H2"]["plasma_state"] == "UNCERTAIN"
    assert by["D2"]["refusal_class"] == "MixedEvidenceError" and by["D2"]["reason"]


def test_map_round_trip_and_tamper(fw, red, case, tmp_path):
    cal, rec = case
    reduced, excl = fw.ingest_records([_hot(rec, rid="H1"), _hot(rec, rid="H2", mode="UNCERTAIN")], {"SYN": cal})
    pts = [fw.map_point(reduced[0], None)]
    assert pts[0]["uncertainty"]["status"] == fw.NOT_EVALUATED and pts[0]["plasma_state_class"] == "H_MODE"
    doc = fw.build_map("SYN-MAP", pts, excl, "P1-REGION-SYN", ["SYN"])
    assert doc["rating_status"] == "TBD_AFTER_IMPEDANCE_MAP" and doc["evidence_status"] == SYN
    p = tmp_path / "map.json"
    sha = fw.write_map(doc, p)
    back = fw.read_map(p)
    assert back == doc and sha == doc["content_sha256"]
    assert back["excluded_records"][0]["record_id"] == "H2"
    for mutate in (lambda m: m["points"][0]["Z_antenna"]["vi_probe"].update(R_ohm=3.0),
                   lambda m: m.update(rating_status="RATED"),
                   lambda m: m["excluded_records"].clear()):
        m = copy.deepcopy(doc)
        mutate(m)
        with pytest.raises(fw.MapFormatError):
            fw.validate_map(m)
    m = copy.deepcopy(doc)
    m["points"][0]["P_plasma_W"] = 1.0
    body = {k: v for k, v in m.items() if k != "content_sha256"}
    m["content_sha256"] = __import__("hashlib").sha256(fw._canon(body).encode("ascii")).hexdigest()
    with pytest.raises(red.ForwardAsPlasmaError):
        fw.validate_map(m)                                          # plasma power never stored
    unc = {"u_gamma_mag": 0.01, "u_VSWR": 0.1, "u_P_net_W": 1.0, "u_P_delivered_W": 1.0,
           "U_Z_antenna_ohm2": [[1.0, 0.0], [0.0, 1.0]], "method": "GUM", "basis": "SYNTHETIC"}
    assert fw.map_point(reduced[0], unc)["uncertainty"]["status"] == "EVALUATED"
    with pytest.raises(fw.UncertaintyMissingError):
        fw.map_point(reduced[0], {"u_gamma_mag": 0.01})


def test_map_refuses_mixing_and_missing_p1_region(fw, red, case):
    cal, rec = case
    reduced, _ = fw.ingest_records([_hot(rec, rid="H1"), _hot(rec, rid="H2", gas="N2")], {"SYN": cal})
    pts = [fw.map_point(r, None) for r in reduced]
    with pytest.raises(fw.MapFormatError):
        fw.build_map("M", pts, [], "P1-REGION-SYN", ["SYN"])        # Ar and N2 never one map
    fake = dict(pts[0], data_class="measured")
    with pytest.raises(red.MixedEvidenceError):
        fw.build_map("M", [pts[0], fake], [], "P1-REGION-SYN", ["SYN"])
    for ref in (None, "PENDING IF-P1-01", "TBD"):
        with pytest.raises(red.SequenceError):
            fw.build_map("M", [pts[0]], [], ref, ["SYN"])
    with pytest.raises(fw.MapFormatError):
        fw.build_map("M", [], [], "P1-REGION-SYN", ["SYN"])


def test_domain_split_out_of_domain_is_not_fail(fw, red, case):
    cal, rec = case
    reduced, _ = fw.ingest_records([_hot(rec, rid="H1")], {"SYN": cal})
    pt = fw.map_point(reduced[0], None)
    region = {"region_id": "SYN-REGION", "factor_ranges": {"P_RF_setpoint_W": [50.0, 150.0],
                                                           "p_chamber_Pa": [0.001, 0.1]}}
    ins, outs, nev = fw.split_by_domain([pt], region)
    assert len(ins) == 1 and not outs and not nev
    ins, outs, nev = fw.split_by_domain([pt], dict(region, factor_ranges={"P_RF_setpoint_W": [150.0, 300.0]}))
    assert outs[0]["status"] == "OUT_OF_DOMAIN" and "FAIL" not in json.dumps(outs)
    ins, outs, nev = fw.split_by_domain([pt], dict(region, factor_ranges={"V_collector_V": [0.0, 10.0]}))
    assert nev[0]["status"] == "NOT_EVALUATED"
    assert fw.split_by_domain([pt], None)[2][0]["status"] == "NOT_EVALUATED"
    with pytest.raises(fw.FrameworkError):
        fw.split_by_domain([pt], {"region_id": "TBD", "factor_ranges": {"p": [0, 1]}})


def test_map_schema_file_generated(fw):
    assert json.loads(MAP_SCHEMA.read_text(encoding="utf-8")) == fw.map_json_schema()
    sc = fw.map_json_schema()
    assert sc["required"] == list(fw.MAP_HEADER_FIELDS)
    assert sc["$defs"]["point"]["required"] == list(fw.MAP_POINT_FIELDS)
    assert sc["properties"]["rating_status"]["const"] == "TBD_AFTER_IMPEDANCE_MAP"


# ------------------------------------------------------------------------------------------------ rating structure
def test_rating_structure_never_rates(fw, red, case):
    cal, rec = case
    env = red.mismatch_envelope([red.reduce_record(rec, {"SYN": cal})], ["DUMMY_LOAD"])
    rs = fw.rating_structure(env, k_rf=1.5, component_margins={"RC-GEN-PFWD": 1.3}, heat_load_option="A")
    assert rs["RF_COMPONENT_RATINGS"] == "TBD_AFTER_IMPEDANCE_MAP"
    for r in rs["rows"]:
        assert r["rating_status"] == "TBD_AFTER_IMPEDANCE_MAP"
        assert isinstance(r["candidate_minimum"], str)               # synthetic envelope -> no candidate numbers
        assert r["candidate_minimum"].startswith(("TBD_AFTER_EVIDENCE", "TBD_OWNER"))
    # code path with a fabricated 'measured' complete envelope (not evidence; tests the gate logic only)
    fake = dict(env, data_classes=["measured"])
    rs2 = fw.rating_structure(fake)
    assert all(r["candidate_minimum"].startswith("TBD_OWNER") for r in rs2["rows"])
    rs3 = fw.rating_structure(fake, component_margins={"RC-GEN-PFWD": 1.3})
    gen = next(r for r in rs3["rows"] if r["id"] == "RC-GEN-PFWD")
    assert gen["candidate_minimum"]["status"] == "CANDIDATE_FOR_OWNER_SELECTION"
    assert gen["candidate_minimum"]["value"] == pytest.approx(1.3 * env["P_forward_W_at_RP_CPL"]["max"])
    heat = next(r for r in rs3["rows"] if r["id"] == "RC-HEAT")
    assert heat["candidate_minimum"].startswith("TBD_OWNER") and heat["owner_input"] == "ICPQ-10"
    assert rs3["RF_COMPONENT_RATINGS"] == "TBD_AFTER_IMPEDANCE_MAP"
    with pytest.raises(fw.RatingInputError):
        fw.rating_structure(fake, component_margins={"RC-GEN-PFWD": 0.9})
    incomplete = dict(fake, coverage=dict(fake["coverage"], complete=False))
    g = next(r for r in fw.rating_structure(incomplete, component_margins={"RC-GEN-PFWD": 1.3})["rows"]
             if r["id"] == "RC-GEN-PFWD")
    assert g["candidate_minimum"].startswith("TBD_AFTER_EVIDENCE")
    assert {r["owner_input"] for r in rs["rows"]} == {"P2Q-10", "ICPQ-10", "ICPQ-11"}


# ------------------------------------------------------------------------------------------------ package content
SEC9_ITEMS = ["reference planes", "VNA calibration", "directional-coupler measurements", "V/I RF measurements",
              "local match settings", "S-parameter data", "antenna impedance", "delivered-power reconstruction",
              "RF line/match loss", "plasma-state classification", "photodiode channel",
              "E/H-mode transition detection", "mismatch envelope", "uncertainty propagation",
              "impedance-map storage", "rating derivation"]


def test_package_framework_section(d, fw):
    f = d["framework"]
    assert [c["a9_6_sec9_item"] for c in f["capabilities"]] == SEC9_ITEMS
    directive = (REPO / "docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md").read_text(
        encoding="utf-8")
    sec9 = directive.split("9. Implement the entire P2 framework now")[1].split("10. Implement P3/P4")[0]
    for s in SEC9_ITEMS:
        assert s in sec9, s
    for c in f["capabilities"]:
        for fn in c["implementation"]:
            m = re.match(r"p2_framework\.(\w+)", fn)
            if m:
                assert hasattr(fw, m.group(1)), fn
    sec14 = directive.split("14. Complete experiment schemas and reducers")[1].split("15. Implement")[0]
    assert len(f["fail_closed"]) == 10
    for x in f["fail_closed"]:
        key = x["a9_6_sec14_item"].split(" -> ")[0].split(" ")[0]
        assert key in sec14
    assert all(s["ok"] is True for s in f["selfcheck"])
    assert {s["evidence_status"] for s in f["selfcheck"]} <= {SYN, "published worked example (code check)"}
    refs = {r["id"]: r for r in f["references"]}
    assert set(refs) == {"REF-TOUCHSTONE11", "REF-WALKER2023", "REF-AN1287-3", "REF-GUM2008", "REF-JCGM101",
                         "REF-JCGM102"}
    for r in refs.values():
        assert re.fullmatch(r"[0-9a-f]{64}", r["sha256"]) and r["url"].startswith("https://") and r["locators"]
    assert f["heat_load_alternatives"]["status"] == "TBD_OWNER" and len(f["heat_load_alternatives"]["alternatives"]) == 2
    assert "IMPLEMENTED_FRAMEWORK_NOT_RUN_ON_DATA" in f["status"]


def test_a96_pins_items_questions_and_statuses(d):
    pins = {p["path"]: p["sha256"] for p in d["decision_pins"]}
    assert pins["docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json"] == \
        "d8d8496f4141a7096496d3a893c95c3db524ca501055a26cc868fb35d0ae9327"
    assert pins["docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md"] == \
        "c6ee26e57ea5ca559f4fa4e4a8809b1aa8f3a217e50c534b943fc3ad99240634"
    items = {it["id"]: it for it in d["items"]}
    for i in ("FW-09", "FW-10", "FW-11", "FW-12", "FW-15", "FW-18", "FW-19", "FW-20"):
        assert items[i]["value"].startswith("TBD - requires") and items[i]["evidence_class"] is None, i
    for i, q in (("FW-18", "ICPQ-11"), ("FW-19", "ICPQ-10"), ("FW-20", "P2Q-10"), ("FW-10", "P2Q-09"),
                 ("FW-12", "P2Q-03")):
        assert q in items[i]["value"], i
    st = json.loads((REPO / "docs/budgets/owner_decisions/owner_questions_state_v3.json").read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in st["rows"]}
    assert rows["ICPQ-10"]["status"] == rows["ICPQ-11"]["status"] == "OPEN"
    assert d["framework"]["heat_load_alternatives"]["question_text"] == rows["ICPQ-10"]["question"]
    qs = {q["id"] for q in d["open_owner_questions"]}
    assert "P2Q-10" in qs and "P2Q-10" not in rows
    applied = {o["ref"]["decision"] for o in d["owner_answers_applied"]
               if isinstance(o["ref"], dict) and o["ref"].get("kind") == "A9.6"}
    assert {"sec. 9", "sec. 14", "sec. 5", "sec. 7"} <= applied
    ids = {x["id"]: x for x in d["interface_demands"]}
    for i in ("IDP2-19", "IDP2-20", "IDP2-21", "IDP2-22"):
        assert i in ids
    assert "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json P3-IF-N04" in ids["IDP2-20"]["direction"]
    assert "PENDING docs/" not in ids["IDP2-20"]["direction"] + ids["IDP2-21"]["direction"]
    assert ids["IDP2-20"]["status"].startswith("TBD_AFTER_IMPEDANCE_MAP")
    assert d["a9_2_statuses_carried"]["RF component ratings"] == "TBD_AFTER_IMPEDANCE_MAP"
    txt = json.dumps(d)
    assert '"PASS"' not in txt
    md = OUT_MD.read_text(encoding="utf-8")
    assert "## 7. P2 framework" in md and "REF-TOUCHSTONE11" in md


def test_framework_hygiene():
    src = FW_PATH.read_text(encoding="utf-8")
    imports = set(re.findall(r"^(?:from|import) ([\w.]+)", src, re.M))
    assert imports <= {"__future__", "cmath", "hashlib", "importlib.util", "json", "math", "random", "fractions",
                       "pathlib"}, imports
    assert "xe" + "_ledger" not in src
    assert not re.search(r"^\s*(?:from|import)\s+(?:abep_sim|archengine)", src, re.M)
    assert "urllib" not in src and "socket" not in src and "subprocess" not in src
    assert '"PASS"' not in src
    test_src = Path(__file__).read_text(encoding="utf-8")
    assert "xe" + "_ledger" not in test_src.replace('"xe" + "_ledger"', "")


def test_p1_handoff_admissibility_fail_closed():
    """XL-01 (P2 side): a P1 handoff that is not REGION_OF_TESTED_POINTS_WITHIN_OWNER_CRITERIA, lacks the criteria
    id, or lacks an envelope factor never opens the hot map; split_by_domain applies the categorical gas sets."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("p2_fw_handoff_test", str(FW_PATH))
    fw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fw)
    env = {"P_fwd_W": [80.0, 120.0], "mdot_Ar_H1_mg_s": [0.9, 1.1], "p_chamber_Pa": [0.01, 0.02],
           "V_collector_V": [-50.0, -30.0]}
    pt = {"operating_point_record_id": "SYN-OP", "match_setting_id": "SYN-M", "h1_point_id": None, "gas": "Ar",
          "gas_mode": "G-REUSE", "Z_ICP": None, "factors": {}}
    h = {"handoff": "IF-P1-01 -> P2 IDP2-01", "evidence_kind": "SYNTHETIC_TEST_ONLY", "status": fw.P1_HANDOFF_ADMISSIBLE,
         "criteria_id": "SYN-CRIT", "points_within_criteria": [pt], "envelope_of_tested_points": env,
         "envelope_note": "x", "dwells": [], "note": "synthetic"}
    ref, region = fw.p1_handoff_admissible(h, "synthetic_test")
    assert region["factor_ranges"]["mdot_hall_anode_mg_s"] == [0.9, 1.1] and "SYN-CRIT" in ref
    assert region["p1_evidence_kind"] == "SYNTHETIC_TEST_ONLY"
    # SW-R2-01: a synthetic P1 handoff never opens a measured P2 map (default target), nor a measured one a synthetic
    with pytest.raises(fw.RED.MixedEvidenceError):
        fw.p1_handoff_admissible(h)
    with pytest.raises(fw.RED.MixedEvidenceError):
        fw.p1_handoff_admissible(dict(h, evidence_kind="MEASURED"), "synthetic_test")
    for kind in ("NO_RECORDS", None, "measured"):
        with pytest.raises(fw.RED.SequenceError):
            fw.p1_handoff_admissible(dict(h, evidence_kind=kind), "synthetic_test")
    mref, _ = fw.p1_handoff_admissible(dict(h, evidence_kind="MEASURED"), "measured")
    assert "evidence MEASURED" in mref
    for bad in (dict(h, status="NOT_EVALUATED"), dict(h, status="NO_TESTED_POINT_WITHIN_CRITERIA"),
                dict(h, status="SOMETHING"), dict(h, criteria_id="TBD"), dict(h, points_within_criteria=[]),
                dict(h, envelope_of_tested_points={k: v for k, v in env.items() if k != "P_fwd_W"}),
                dict(h, envelope_of_tested_points=dict(env, P_fwd_W=[120.0, 80.0])), None,
                {k: v for k, v in h.items() if k != "evidence_kind"}):
        with pytest.raises(fw.RED.SequenceError):
            fw.p1_handoff_admissible(bad, "synthetic_test")
    pts = [{"record_id": "A", "factors": {"P_RF_setpoint_W": 100.0, "mdot_hall_anode_mg_s": 1.0, "p_chamber_Pa": 0.015,
                                          "V_collector_V": -40.0, "gas": "Ar", "gas_mode": "G-REUSE"}},
           {"record_id": "B", "factors": {"P_RF_setpoint_W": 100.0, "mdot_hall_anode_mg_s": 1.0, "p_chamber_Pa": 0.015,
                                          "V_collector_V": -40.0, "gas": "Ar"}}]
    ins, outs, nev = fw.split_by_domain(pts, region)
    assert [p["record_id"] for p in ins] == ["A"] and [p["record_id"] for p in nev] == ["B"] and not outs



# ------------------------------------------------------------------ A9.6 sec. 18 consolidated verification, repair round 1
def test_sw04_uncertainty_helpers_refuse_invalid_inputs(fw):
    """SW-04: non-PSD / negative / non-finite covariances and inputs, negative u, eta > 1, |Gamma| > 1 are refused."""
    f = lambda x: [x[0] + x[1]]
    for bad in ([[0.01, 0.5], [0.5, 0.01]], [[-0.01, 0.0], [0.0, 0.01]]):
        with pytest.raises(fw.UncertaintyMissingError):
            fw.propagate_linear(f, [1.0, 1.0], bad)
        with pytest.raises(fw.UncertaintyMissingError):
            fw.propagate_mc(f, [1.0, 1.0], bad, n_trials=1000, seed=1)
    for x in ([float("nan"), 1.0], [float("inf"), 1.0]):
        with pytest.raises(fw.FrameworkError):
            fw.propagate_linear(f, x, [[0.01, 0.0], [0.0, 0.01]])
    with pytest.raises(fw.UncertaintyMissingError):
        fw.gamma_vswr_pnet_uncertainty(100.0, -1.0, 4.0, -1.0, 0.0)
    for args in ((100.0, 1.0, 1.5, 0.1), (100.0, 1.0, 0.9, -0.1), (-5.0, 1.0, 0.9, 0.01)):
        with pytest.raises(fw.FrameworkError):
            fw.p_delivered_uncertainty(*args)
    with pytest.raises(fw.FrameworkError):
        fw.z_from_gamma_uncertainty(2 + 0j, [[1e-4, 0.0], [0.0, 1e-4]], 50.0)
    assert fw.p_delivered_uncertainty(100.0, 1.0, 0.9, 0.01)["P_delivered_W"] == pytest.approx(90.0)


def test_sw09_mc_coverage_order_statistic_and_type_checks(fw):
    """SW-09: the JCGM 101 7.7.2 order statistics [y_(r), y_(r+q)] are exact for a deterministic identity case;
    a bool seed and a None sweep index are refused with framework errors."""
    import random as _random
    n = 1000
    out = fw.propagate_mc(lambda x: [x[0]], [0.0], [[1.0]], n_trials=n, seed=7)
    rng = _random.Random(7)
    zs, spare = [], None
    for _ in range(n):                       # replay the documented Box-Muller stream (one input: spare unused)
        if spare is not None:
            zs.append(spare)
            spare = None
            continue
        u1 = 1.0 - rng.random()
        u2 = rng.random()
        rad = math.sqrt(-2.0 * math.log(u1))
        zs.append(rad * math.cos(2 * math.pi * u2))
        spare = rad * math.sin(2 * math.pi * u2)
    col = sorted(zs)
    q, r = 950, 25                           # q = int(0.95 * 1000) (integer pM), r = (M - q) / 2 (JCGM 101 7.7.2)
    assert out["coverage_interval_95"][0] == [col[r - 1], col[r + q - 1]]
    with pytest.raises(fw.FrameworkError):
        fw.propagate_mc(lambda x: [x[0]], [0.0], [[1.0]], n_trials=1000, seed=True)


def test_sw09_sweep_index_type_checked(fw):
    pts = _sweep("up", UP)
    pts[0]["index"] = None
    with pytest.raises(fw.FrameworkError):
        fw.detect_eh_transitions(pts, CRIT)


def test_met07_r1_shifted_eta_pred_cannot_flip_inconsistent_to_verified(fw, red):
    """Consolidated verification MET-07-R1: u_eta_pred is used once (in u_c); a caller-shifted eta_pred is refused
    and a record carrying one is rejected by the reducer, so an INCONSISTENT check never becomes VERIFIED."""
    cal = _cal_from_touchstone(fw, red, _line(30.0), fw.ladder_abcd(ELEMENTS))
    eta_model = red.loss_model_prediction(cal, TS_MODEL)[0]
    bad = _verify(fw, red, cal, TS_MODEL, "VX1", eta_meas=0.9, u_eta_pred=0.06, k=1.0)
    assert bad["status"] != red.LOSS_VERIFIED
    with pytest.raises(fw.FrameworkError):
        _verify(fw, red, cal, TS_MODEL, "VX2", eta_meas=0.9, u_eta_pred=0.06, k=1.0, eta_pred=eta_model - 0.06)
    forged = dict(_verify(fw, red, cal, TS_MODEL, "VX3", u_eta_pred=0.06, k=1.0))
    forged.update(eta_measured=0.9, eta_predicted=eta_model - 0.06)
    forged["normalized_statistic"] = red.loss_statistic(forged["comparison"], 0.9, forged["u_eta_measured"],
                                                        eta_model - 0.06, 0.06)
    ok, why = red.loss_verification_status(forged, cal, tuning_state_id="TS1")
    assert not ok and "MET-07" in why
    with pytest.raises(fw.CriteriaMissingError):
        _verify(fw, red, cal, TS_MODEL, "VX4", u_eta_pred=0.06, u_eta_pred_basis_id=None)
    nobasis = dict(_verify(fw, red, cal, TS_MODEL, "VX5", u_eta_pred=0.06))
    nobasis["u_eta_predicted_basis_id"] = None
    ok, why = red.loss_verification_status(nobasis, cal, tuning_state_id="TS1")
    assert not ok and "registration" in why


def test_met07_r2_registrations_resolved_and_evidence_recomputed(fw, red):
    """Consolidated verification MET-07-R2: k and u_eta_pred resolve in the calibration set's registrations (never
    self-declared ids), eta/u measured are recomputed from the carried powers, and a declared bound carries u_p = 0."""
    cal = _cal_from_touchstone(fw, red, _line(30.0), fw.ladder_abcd(ELEMENTS))
    with pytest.raises(fw.CriteriaMissingError):                        # unregistered id
        _verify(fw, red, cal, TS_MODEL, "VR1", k=100.0, k_reg="x")
    with pytest.raises(fw.CriteriaMissingError):                        # registered id, other value
        _verify(fw, red, cal, TS_MODEL, "VR2", k=5.0, k_reg="SYN-K-REG-01")
    with pytest.raises(fw.CriteriaMissingError):                        # unregistered u basis
        _verify(fw, red, cal, TS_MODEL, "VR3", eta_meas=0.9, u_eta_pred=0.08, u_eta_pred_basis_id="x")
    for ph in ("N/A", "NONE", "-", "ANY"):
        assert not red._ref_ok(ph)
    bad = _verify(fw, red, cal, TS_MODEL, "VR4", eta_meas=0.9, u_eta_pred=0.06, k=1.0)
    assert bad["status"] != red.LOSS_VERIFIED
    for forge in (dict(status=red.LOSS_VERIFIED, u_eta_predicted=0.2, u_eta_predicted_basis_id="ANY"),
                  dict(status=red.LOSS_VERIFIED, k=5.0, k_registration_id="ANY"),
                  dict(status=red.LOSS_VERIFIED, u_eta_measured=0.2)):
        f = dict(bad, **forge)
        ok, why = red.loss_verification_status(f, cal, tuning_state_id="TS1")
        assert not ok, forge
    lb = _verify(fw, red, cal, LB_MODEL, "VR5", eta_meas=0.6)
    f = dict(lb, status=red.LOSS_VERIFIED, u_eta_predicted=0.5, u_eta_predicted_basis_id="SYN-SPARAM-UNC-06")
    ok, why = red.loss_verification_status(f, cal, loss_bound_id="LB1")
    assert not ok and "declared bound" in why
    c2 = copy.deepcopy(cal)
    del c2["loss_check_registrations"]
    ok, why = red.loss_verification_status(c2["loss_verification"], c2, tuning_state_id="TS1")
    assert not ok and "loss_check_registrations" in why
