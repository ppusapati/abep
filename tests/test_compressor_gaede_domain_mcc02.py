"""MCC-02 (owner decision A9.9 S2.5, finding F3-01): Gaede clipping.

The unclipped Gaede characteristic is preserved and reported per stage and species; a state with K_unclipped < 1
(throughput above stage capacity) is flagged OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY, its clipped K = 1 is only a labelled
diagnostic, size_for never selects it, and the gas path fails closed on it.
"""
import math

import pytest

from abep_sim.compressor import DragCompressor

MD = {"O": 0.45e-6, "N2": 0.50e-6, "O2": 0.05e-6}


def _reference_K(comp, p_in, md):
    """Independent re-derivation of the unclipped linear Gaede characteristic for the first turbo row."""
    from abep_sim.constants import K_B, M_SPECIES
    nflow = {s: md[s] / M_SPECIES[s] for s in md}
    ntot = sum(nflow.values())
    u_t = comp.turbo_radius_m * comp.rpm * 2 * math.pi / 60.0
    S_t = comp.turbo_kS * u_t * comp.turbo_area_m2
    out = {}
    for s in md:
        cb = math.sqrt(8 * K_B * comp.T_gas_K / (math.pi * M_SPECIES[s]))
        K0 = math.exp(comp.turbo_kK * u_t / cb)
        Q = nflow[s] * K_B * comp.T_gas_K
        out[s] = K0 - (K0 - 1.0) * Q / (S_t * p_in * nflow[s] / ntot)
    return out


def test_overloaded_stage_reports_unclipped_K_and_out_of_domain_status():
    c = DragCompressor(turbo_area_m2=0.05, turbo_radius_m=0.12, turbo_rows=1, n_stages=1, rpm=20000)
    r = c.run(0.005, MD, self_consistent=False)
    ref = _reference_K(c, 0.005, MD)
    assert all(ref[s] < 1.0 for s in MD)                                  # physically overloaded
    for s in MD:
        assert r["gaede_K_unclipped"]["turbo_row_1"][s] == pytest.approx(ref[s], rel=1e-12)
    assert r["gaede_domain_ok"] is False
    assert r["gaede_status"] == "OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY"
    assert r["gaede_clipped_values_are_diagnostic"] is True
    assert "turbo_row_1:N2" in r["gaede_out_of_domain"] and r["gaede_K_unclipped_min"] < 1.0
    st = [g for g in r["gaede_stages"] if g["stage"] == "turbo_row_1"]
    assert {g["species"] for g in st} == set(MD)
    for g in st:
        assert g["in_domain"] is False and g["K_clipped_diagnostic"] == 1.0 and g["load_ratio"] > 1.0
    # drag stage recorded too (per stage and species)
    assert set(r["gaede_K_unclipped"]["drag_stage_1"]) == set(MD)


def test_in_domain_stage_is_unclipped_and_numerically_unchanged():
    c = DragCompressor(turbo_area_m2=0.45, turbo_radius_m=0.40, rotor_material="CFRP", turbo_rows=2, n_stages=0, rpm=20000)
    r = c.run(0.005, MD, self_consistent=False)
    assert r["gaede_domain_ok"] is True and r["gaede_status"] == "IN_DOMAIN"
    assert r["gaede_out_of_domain"] == [] and r["gaede_clipped_values_are_diagnostic"] is False
    for g in r["gaede_stages"]:
        assert g["in_domain"] and g["K_clipped_diagnostic"] is None and 1.0 <= g["K_unclipped"] <= g["K0"]
    # the cascade uses the unclipped K: CR_by_species = product of the per-stage unclipped values
    for s in MD:
        prod = 1.0
        for stage in r["gaede_K_unclipped"].values():
            prod *= stage[s]
        assert r["CR_by_species"][s] == pytest.approx(prod, rel=1e-12)


def test_run_self_consistent_carries_gaede_fields():
    c = DragCompressor(turbo_area_m2=0.05, turbo_radius_m=0.12, turbo_rows=1, n_stages=0, rpm=20000)
    r = c.run(0.005, MD)
    assert r["gaede_status"] == "OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY" and "solver_status" in r


def test_size_for_never_selects_out_of_domain_state():
    small = DragCompressor(turbo_area_m2=0.05, turbo_radius_m=0.12).size_for(0.005, MD, 5)
    assert small["sized"] is False and small["gaede_domain_ok"] is False
    assert small["gaede_status"] == "OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY"
    big = DragCompressor(turbo_area_m2=0.45, turbo_radius_m=0.40, rotor_material="CFRP").size_for(0.005, MD, 5)
    assert big["sized"] is True and big["gaede_domain_ok"] is True
    assert "n_rejected_out_of_gaede_domain" in big


def test_size_for_rejects_cr_reached_through_clipped_stage(monkeypatch):
    """A layout that meets CR only while some stage is overloaded is counted and skipped, not selected."""
    c = DragCompressor(turbo_area_m2=0.45, turbo_radius_m=0.40, rotor_material="CFRP")
    orig = DragCompressor.run

    def run(self, p, md, self_consistent=True):
        r = orig(self, p, md, self_consistent)
        if self.turbo_rows == 1:                     # pretend the 1-row layouts are overloaded
            r = dict(r, gaede_domain_ok=False, gaede_status="OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY")
        return r
    monkeypatch.setattr(DragCompressor, "run", run)
    r = c.size_for(0.005, MD, 1.2, max_turbo_rows=2, max_drag_stages=0)   # 1 row reaches CR 1.35 at 10000 rpm
    assert r["sized"] and r["turbo_rows"] == 2 and r["n_rejected_out_of_gaede_domain"] >= 1


def test_gas_path_fails_closed_out_of_gaede_domain():
    from abep_sim.system import Config, evaluate
    from abep_sim.intake import IntakeParams, CompressorParams
    r = evaluate(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=1.3, accommodation=0.8, use_tpmc=True, L_over_d=5),
                        CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True))
    assert r["comp_gaede_status"] == "OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY" and r["comp_gaede_domain_ok"] is False
    assert r["comp_gaede_K_unclipped_min"] < 1.0 and r["comp_gaede_out_of_domain"]
    assert r["gaspath_domain_status"] == "OUT_OF_MODEL_DOMAIN"
    assert r["gaspath_out_of_domain"] == ["compressor_gaede_stage_capacity"]
    assert r["chk_compressor_feasible"] is False
    ok = evaluate(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5),
                         CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True))
    assert ok["comp_gaede_status"] == "IN_DOMAIN" and ok["gaspath_domain_status"] == "IN_DOMAIN"


def test_archengine_flags_and_arch_compare_refuses_out_of_domain_state():
    from abep_sim import archengine as AE
    from abep_sim import arch_compare as ac
    gf = AE.make_gas_fn()
    good = gf(0.7, 0.1)
    assert good["gaspath_domain_status"] == "IN_DOMAIN" and good["gaspath_out_of_domain"] == ""
    bad = dict(good, gaspath_domain_status="OUT_OF_MODEL_DOMAIN", gaspath_out_of_domain="compressor_gaede_stage_capacity")
    with pytest.raises(ac.SpecError, match="gaspath_domain_status"):
        ac.UpstreamState.from_gas_path(bad, "x")
    from abep_sim.mission_env import Spacecraft
    A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    r = AE.close_architecture(A["hall_internal+hall+lab6_xe"], lambda area, p: bad, Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5),
                              AE.DesignConstraints(2500.0), gas_vars={"area": [0.7], "p_level": [0.1]}, keep_candidates=False)
    if r["status"] == "OK":
        assert r["gaspath_domain_status"] == "OUT_OF_MODEL_DOMAIN" and r["evidence_admissible"] is False
