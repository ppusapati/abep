"""Transitional-regime compressor candidate (owner A9.13 S6.8 OQ-F3-03 / S6.11 OQ-F4-02).

- Eq. (1) is re-derived independently here (integration of dp/dx) and checked against the module;
- the source's stated limits (continuum dp, free-molecular K, maximum throughput) are reproduced;
- every output is CANDIDATE_NOT_ADMITTED, can never be used as design evidence, and > 0.1 Pa is out of domain;
- missing/invalid inputs raise (no hidden defaults); documented gaps refuse;
- the overlap-regime consistency check against DragCompressor behaves as analysed and never mutates the caller's object;
- the evidence package is reproduced exactly by its builder and is internally consistent.
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

from abep_sim import compressor_transitional as ct
from abep_sim.compressor import DragCompressor
from abep_sim.constants import K_B, M_SPECIES

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "evidence" / "compressor_transitional"
JSON = DIR / "compressor_transitional_evidence_v1.json"


def _stage(**kw):
    base = dict(gap_m=3e-3, length_m=0.05, width_m=12e-3, wall_speed_mps=300.0, sigma=0.8,
                sigma_evidence_class="assumed", sigma_source="test value")
    base.update(kw)
    return ct.DragChannelStage(**base)


def _length_numeric(stage, gas, T, p1, p2, mdot, n=20000):
    """Independent derivation: dx/dp = (p d^2 + 6 k mu c0 d) / (6 mu (p w - 2 g R T / d)), trapezoid in ln p."""
    mu = ct.viscosity_Pa_s(gas, T)
    R = K_B / M_SPECIES[gas]
    c0 = math.sqrt(math.pi * R * T / 2)
    k = (2 - stage.sigma) / stage.sigma
    g = mdot / stage.width_m
    d, w = stage.gap_m, stage.wall_speed_mps

    def dxdp(p):
        return (p * d * d + 6 * k * mu * c0 * d) / (6 * mu * (p * w - 2 * g * R * T / d))

    a, b = math.log(p1), math.log(p2)
    h = (b - a) / n
    s = 0.0
    for i in range(n + 1):
        p = math.exp(a + i * h)
        f = dxdp(p) * p
        s += f * (0.5 if i in (0, n) else 1.0)
    return s * h


@pytest.mark.parametrize("gas", ["N2", "O2"])
@pytest.mark.parametrize("p1,p2,frac", [(1e-3, 5e-3, 0.0), (0.05, 2.0, 0.2), (1.0, 50.0, 0.1)])
def test_eq1_matches_independent_integration(gas, p1, p2, frac):
    st = _stage()
    mdot = frac * ct.max_throughput_kgps(st, gas, 300.0, p1)
    L_mod = ct.stage_length_m(st, gas, 300.0, p1, p2, mdot)
    L_num = _length_numeric(st, gas, 300.0, p1, p2, mdot)
    assert L_mod == pytest.approx(L_num, rel=1e-6)


def test_free_molecular_limit_from_source():
    st = _stage(length_m=0.01)
    r = ct.solve_outlet_pressure(st, "N2", 300.0, 1e-6, 0.0)
    lnK = math.log(r.candidate_values["compression_ratio"])
    expect = st.sigma * st.wall_speed_mps * st.length_m / ((2 - st.sigma) * ct.c0_mps("N2", 300.0) * st.gap_m)
    assert lnK == pytest.approx(expect, rel=1e-6)


def test_continuum_limit_from_source():
    st = _stage(length_m=0.05)
    mu = ct.viscosity_Pa_s("N2", 300.0)
    dp_c = 6 * mu * st.wall_speed_mps * st.length_m / st.gap_m ** 2
    devs = []
    for p in (1e4, 1e5):   # residual = slip correction, shrinking ~1/p
        r = ct.solve_outlet_pressure(st, "N2", 300.0, p, 0.0)
        devs.append(abs((r.candidate_values["p_out_Pa"] - p) / dp_c - 1))
    assert devs[1] < 1e-3 and devs[1] < devs[0] / 5


def test_max_throughput_and_capacity_refusal():
    st = _stage()
    cap = ct.max_throughput_kgps(st, "N2", 300.0, 0.01)
    R = K_B / M_SPECIES["N2"]
    assert cap == pytest.approx(0.01 * 300.0 * 3e-3 * 12e-3 / (2 * R * 300.0))
    r = ct.solve_outlet_pressure(st, "N2", 300.0, 0.01, cap * 1.0001)
    assert r.status == ct.ST_THROUGHPUT and "p_out_Pa" not in r.candidate_values
    with pytest.raises(ct.OutOfModelDomainError):
        ct.stage_length_m(st, "N2", 300.0, 0.01, 0.02, cap * 2)


def test_inlet_and_outlet_solvers_are_inverse():
    st = _stage()
    md = 0.2 * ct.max_throughput_kgps(st, "O2", 350.0, 0.05)
    r1 = ct.solve_outlet_pressure(st, "O2", 350.0, 0.05, md)
    r2 = ct.solve_inlet_pressure(st, "O2", 350.0, r1.candidate_values["p_out_Pa"], md)
    assert r2.candidate_values["p_in_Pa"] == pytest.approx(0.05, rel=1e-8)


def test_compression_falls_toward_viscous_regime():
    st = _stage()
    ks = [ct.solve_outlet_pressure(st, "N2", 300.0, p, 0.0).candidate_values["compression_ratio"]
          for p in (1e-3, 1e-1, 10.0, 1e3)]
    assert all(a > b for a, b in zip(ks, ks[1:]))


def test_every_output_is_candidate_not_admitted():
    st = _stage(length_m=0.002)
    for p in (1e-4, 0.5):
        r = ct.solve_outlet_pressure(st, "N2", 300.0, p, 0.0)
        assert r.evidence_status == "CANDIDATE_NOT_ADMITTED" and r.valid_design_evidence is False
        assert r.to_dict()["evidence_status"] == "CANDIDATE_NOT_ADMITTED"
        with pytest.raises(ct.NotAdmittedError):
            r.as_design_evidence()
    with pytest.raises(ct.NotAdmittedError):
        dataclasses.replace(r, valid_design_evidence=True)
    with pytest.raises(ct.NotAdmittedError):
        dataclasses.replace(r, evidence_status="ADMITTED")


def test_above_0p1_Pa_is_not_evaluated_out_of_domain():
    st = _stage(length_m=0.002)
    lo = ct.solve_outlet_pressure(st, "N2", 300.0, 1e-3, 0.0)
    assert lo.candidate_values["p_out_Pa"] <= 0.1
    assert lo.architecture_point_status == ct.ARCH_NOT_DESIGN_EVIDENCE
    hi = ct.solve_outlet_pressure(st, "N2", 300.0, 0.08, 0.0)
    assert hi.candidate_values["p_out_Pa"] > 0.1
    assert hi.architecture_point_status == "NOT_EVALUATED_OUT_OF_DOMAIN"
    assert "PRESSURE_ABOVE_0.1_Pa_FREE_MOLECULAR_PRODUCTION_DOMAIN" in hi.domain_flags
    c = ct.cascade([st, st], "N2", 300.0, 0.05, 0.0)
    assert c.architecture_point_status == "NOT_EVALUATED_OUT_OF_DOMAIN"
    assert "INTERSTAGE_LEAKAGE_NOT_MODELLED" in c.domain_flags


def test_domain_limit_matches_production_f3_constant():
    from abep_sim.design import compressor_synthesis as cs
    assert ct.P_FREE_MOLECULAR_LIMIT_PA == cs.P_MOLECULAR_LIMIT_PA


@pytest.mark.parametrize("kw", [dict(gap_m=0), dict(length_m=-1), dict(width_m=float("nan")), dict(sigma=0.0),
                                dict(sigma=1.2), dict(sigma_evidence_class="handbook"), dict(sigma_source=" ")])
def test_invalid_stage_raises(kw):
    with pytest.raises(ct.OutOfModelDomainError):
        _stage(**kw)


def test_no_default_sigma():
    with pytest.raises(TypeError):
        ct.DragChannelStage(gap_m=1e-3, length_m=0.1, width_m=1e-2, wall_speed_mps=300.0)


@pytest.mark.parametrize("gas,T", [("O", 300.0), ("Xe", 300.0), ("N2", 150.0), ("O2", 600.0)])
def test_gas_and_temperature_domain(gas, T):
    with pytest.raises(ct.OutOfModelDomainError):
        ct.solve_outlet_pressure(_stage(), gas, T, 1e-3, 0.0)


def test_turbomolecular_transitional_is_a_refusing_stub():
    with pytest.raises(ct.NotEvaluatedError):
        ct.turbomolecular_row_transitional(p_in_Pa=1.0)


def test_viscosity_table_equals_nist_snapshots():
    for gas, fn in (("N2", "nist_webbook_N2_isobar_0.001bar_200-500K.tsv"),
                    ("O2", "nist_webbook_O2_isobar_0.001bar_200-500K.tsv")):
        lines = (DIR / "sources" / fn).read_text(encoding="utf-8").strip().splitlines()
        head = lines[0].split("\t")
        iT, iv = head.index("Temperature (K)"), head.index("Viscosity (uPa*s)")
        rows = tuple((float(c[iT]), float(c[iv])) for c in (ln.split("\t") for ln in lines[1:]))
        assert rows == ct.VISCOSITY_TABLE_uPa_s[gas]
    assert ct.viscosity_Pa_s("N2", 325.0) == pytest.approx(0.5 * (17.877 + 20.107) * 1e-6)


def test_sigma_xi_mapping():
    for xi in (0.1, 0.4, 0.6, 2 / math.pi):
        s = ct.sigma_from_free_molecular_xi(xi)
        assert 2 * s / (math.pi * (2 - s)) == pytest.approx(xi)
    with pytest.raises(ct.OutOfModelDomainError):
        ct.sigma_from_free_molecular_xi(0.7)


def test_consistency_check_overlap():
    base = DragCompressor()
    cfg = dataclasses.replace(base, L_per_stage_m=0.005)
    snapshot = dataclasses.asdict(cfg)
    # zero-flow: free-molecular compressions coincide; residual is the small viscous/slip correction
    r0 = ct.compare_with_free_molecular(cfg, "N2", 1e-4, 1e-18)
    assert r0["comparable"] and r0["in_overlap_regime"]
    assert r0["lnK0_free_molecular_DragCompressor"] == pytest.approx(r0["lnK0_free_molecular_candidate_limit"],
                                                                     rel=1e-12)
    assert abs(r0["lnK_rel_diff_candidate_vs_DragCompressor"]) < 1e-4
    # finite throughput: DragCompressor speed is xi times the plane-channel speed -> predicted K differ as analysed
    st = ct.DragChannelStage(gap_m=cfg.h_mm * 1e-3, length_m=cfg.L_per_stage_m, width_m=cfg.w_mm * 1e-3,
                             wall_speed_mps=cfg.u, sigma=r0["sigma_mapped"], sigma_evidence_class="model-derived",
                             sigma_source="xi mapping")
    f = 0.1
    md = f * ct.max_throughput_kgps(st, "N2", cfg.T_gas_K, 1e-4)
    r = ct.compare_with_free_molecular(cfg, "N2", 1e-4, md)
    K0 = math.exp(r["lnK0_free_molecular_DragCompressor"])
    assert r["K_DragCompressor"] == pytest.approx(K0 - (K0 - 1) * f / cfg.xi, rel=1e-6)
    assert r["K_candidate"] == pytest.approx(K0 - (K0 - 1) * f, rel=1e-3)
    assert r["speed_ratio_DragCompressor_over_candidate"] == cfg.xi
    assert r["S0_DragCompressor_m3_s"] == pytest.approx(cfg.xi * r["S0_candidate_plane_channel_m3_s"])
    assert r["evidence_status"] == "CANDIDATE_NOT_ADMITTED" and r["valid_design_evidence"] is False
    # the caller's compressor is never mutated
    assert dataclasses.asdict(cfg) == snapshot


def test_consistency_check_flags_out_of_domain_default_geometry():
    r = ct.compare_with_free_molecular(DragCompressor(), "N2", 1e-3, 1e-15)
    assert r["in_overlap_regime"] is False and r["comparable"] is False
    assert r["architecture_point_status"] == "NOT_EVALUATED_OUT_OF_DOMAIN"
    with pytest.raises(ct.OutOfModelDomainError):
        ct.compare_with_free_molecular(DragCompressor(), "N2", 1e-3, 0.0)


def test_consistency_check_flags_clipped_characteristic():
    cfg = dataclasses.replace(DragCompressor(), L_per_stage_m=0.005)
    st = ct.DragChannelStage(gap_m=3e-3, length_m=0.005, width_m=12e-3, wall_speed_mps=cfg.u, sigma=0.97,
                             sigma_evidence_class="model-derived", sigma_source="x")
    md = 0.8 * ct.max_throughput_kgps(st, "N2", cfg.T_gas_K, 1e-3)   # above xi * capacity
    r = ct.compare_with_free_molecular(cfg, "N2", 1e-3, md)
    assert r["DragCompressor_characteristic_clipped"] is True and r["comparable"] is False


# ------------------------------------------------------------------------------------------- evidence package
@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("ct_builder", DIR / "build_compressor_transitional_evidence.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON.read_text(encoding="utf-8"))


def test_builder_check_reproduces(builder):
    assert builder.main(["--check"]) == 0


def test_decision_pinned(doc):
    od = doc["owner_decision"]
    for key in ("json", "verbatim_md"):
        p = ROOT / od[key]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == od[key + "_sha256"]
    assert set(od["questions"]) == {"OQ-F3-03", "OQ-F4-02"}
    assert od["questions"]["OQ-F3-03"]["answer"] == "MODEL_AND_TEST_PARALLEL_FAIL_CLOSED"


def test_source_register_discipline(doc):
    ids = [s["id"] for s in doc["source_register"]]
    assert len(ids) == len(set(ids))
    for s in doc["source_register"]:
        for k in ("citation", "access", "quantities", "regime", "validation_in_source", "use"):
            assert s.get(k), (s["id"], k)
        assert not s["access"].upper().startswith("PAYWALL_BYPASS")
        if s["use"].startswith("IMPLEMENTED") or s["use"].startswith("VISCOSITY") or s["use"].startswith("Kn"):
            assert s["access"].startswith("OPEN"), s["id"]
    implemented = [s for s in doc["source_register"] if s["use"].startswith("IMPLEMENTED")]
    assert [s["id"] for s in implemented] == ["CT-S01"]
    assert "lxcat" not in json.dumps(doc["source_register"]).lower()


def test_status_and_admission_plan(doc):
    assert doc["evidence_status"] == "CANDIDATE_NOT_ADMITTED" and doc["valid_design_evidence"] is False
    ap = doc["admission_plan"]
    assert {r["route"] for r in ap["routes"]} == {"A_HARDWARE", "B_HELD_OUT_PUBLISHED"}
    assert "NOT_EVALUATED_OUT_OF_DOMAIN" in ap["until_admitted"]
    assert any("TBD" in s for s in ap["pre_registration_before_any_comparison"])
    gaps = {g["id"] for g in doc["gap_memo"]}
    assert {"GAP-01", "GAP-05"} <= gaps


def test_coefficients_cited(doc):
    for name, c in doc["coefficient_register"].items():
        assert c["source"], name
    assert doc["coefficient_register"]["sigma"]["value"] is None   # no default


def test_missing_input_raises(builder, tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "SNAPSHOTS", {"N2": tmp_path / "missing.tsv"})
    with pytest.raises(FileNotFoundError):
        builder.coefficient_register()
    monkeypatch.setattr(builder, "DECISION_JSON", tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):
        builder.decisions()
