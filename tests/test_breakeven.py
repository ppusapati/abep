"""Tests for abep_sim/breakeven.py (architecture break-even relations; no absolute Hall prediction).

Hand-calculated points are derived in docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md (section 12).
Every numeric input here is a test value, not evidence.
"""
import dataclasses
import inspect
import math
import sys
import types

import pytest

from abep_sim import breakeven as b
from abep_sim.constants import AMU, E_CHARGE

N2 = b.IonMix((b.IonSpecies("N2+", 28.014, 1, 1.0),))
OP = b.IonMix((b.IonSpecies("O+", 15.999, 1, 1.0),))
XE = b.IonMix((b.IonSpecies("Xe+", 131.29, 1, 1.0),))
ZERO_COMMON = {k: 0.0 for k in b.COMMON_NON_DISCHARGE}


def ref_n2(eta_u=0.5, eta_b=0.7, eta_v=0.9, V=300.0, mdot=None, eta_ppu=1.0, mix=N2, gamma=0.9):
    if mdot is None:                 # I_b0 = 1 A
        mdot = 1.0 / (eta_u * mix.coulomb_per_kg)
    return b.HallReference(mdot_kg_s=mdot, V_d_V=V, eta_u=eta_u, eta_b=eta_b, eta_v=eta_v, gamma_div=gamma,
                           eta_ppu_discharge=eta_ppu, mix=mix)


def resp(alpha, chi, eta_v_s=0.9, mix=N2):
    return b.PreionResponse(alpha=alpha, chi=chi, eta_v_delivered=eta_v_s, mix_delivered=mix)


def ov(P, arch="rf_hall", fixed=0.0):
    src = {"rf_source": P} if arch == "rf_hall" else {"ecr_source": P, "ecr_magnet": fixed}
    return b.BusOverhead(arch=arch, source_bus_W=src, delta_common_bus_W=dict(ZERO_COMMON),
                         interstage_loss_bus_W=0.0, extra_ppu_bus_W=0.0)


ADD = resp(1.0, 0.0)
COST = resp(1.0, 1.0)


# ---------------------------------------------------------------------------------------------------- limiting cases
def test_zero_source_power_needs_zero_utilization_gain():
    for r in (ADD, COST, resp(0.5, 0.3), resp(1.0, 1.0, eta_v_s=1.0)):
        out = b.required_utilization_gain(ref_n2(), r, ov(0.0))
        assert out["status"] == "OK" and out["delta_eta_u_star"] == 0.0 and out["delta_s_star"] == 0.0
        e = b.evaluate_arm(ref_n2(), r, ov(0.0), 0.0)
        assert abs(e["equal_thrust"]["net_bus_saving_W"]) < 1e-9
        assert abs(e["equal_bus_power"]["thrust_gain_fraction"]) < 1e-12


def test_eta_transport_to_zero_is_infeasible():
    ref = ref_n2()
    ev = lambda v, u: b.Evidenced(v, u, "assumed", "unit test")
    sup = b.supremum_breakeven_delivered_cost(ref, COST, 0.0, 64)["sup_W_per_A"]
    for et in (1e-3, 1e-6, 1e-9):
        out = b.place_evidence(ref, COST, 0.0, ev(1.0, "W/A"), ev(et, "1"), 64)   # even a 1 W/A source
        assert out["status"] == "CANNOT_BREAK_EVEN_IN_MODEL_FAMILY"
        # the source-side break-even cost eta_t * C_del* vanishes with eta_t
        assert et * sup < 1.0
    with pytest.raises(b.BreakevenInputError):
        b.place_evidence(ref, COST, 0.0, ev(1.0, "W/A"), ev(0.0, "1"), 64)


def test_overhead_at_or_above_discharge_power_is_infeasible():
    ref = ref_n2()
    P0 = b.hall_only_state(ref)["P_d_bus_W"]
    for f in (1.0, 1.5):
        out = b.required_utilization_gain(ref, COST, ov(f * P0))
        assert out["status"] == "INFEASIBLE_OVERHEAD_GE_DISCHARGE" and out["delta_eta_u_star"] is None
    e = b.evaluate_arm(ref, COST, ov(1.2 * P0), 0.1)
    assert e["equal_bus_power"]["feasible"] is False and not e["master_breaks_even"]


def test_utilization_cap_is_infeasible():
    ref = ref_n2(eta_u=0.9)
    P0 = b.hall_only_state(ref)["P_d_bus_W"]
    out = b.required_utilization_gain(ref, ADD, ov(0.5 * P0))   # needs 0.9 * 0.5/0.5 = 0.9 > 1 - 0.9
    assert out["status"] == "INFEASIBLE_UTILIZATION_CAP"
    assert out["delta_eta_u_star"] == pytest.approx(0.9)


# ---------------------------------------------------------------------------------------------- hand-calculated points
def test_hand_add_only_required_gain():
    ref = ref_n2()
    P0 = b.hall_only_state(ref)["P_d_bus_W"]
    assert P0 == pytest.approx(300.0 / 0.7)                       # I_b = 1 A, eta_b = 0.7, eta_ppu = 1
    out = b.required_utilization_gain(ref, ADD, ov(0.1 * P0))
    assert out["delta_eta_u_star"] == pytest.approx(0.5 * 0.1 / 0.9, rel=1e-12)          # eta_u0 w/(1-w)
    assert out["delta_eta_u_star"] == pytest.approx(b.required_utilization_gain_add_only_closed_form(0.5, 0.1))
    assert out["V_d_ratio_at_breakeven"] == pytest.approx(0.81, rel=1e-12)                 # (1-w)^2


def test_hand_cost_offset_required_gain():
    ref = ref_n2()
    P0 = b.hall_only_state(ref)["P_d_bus_W"]
    out = b.required_utilization_gain(ref, COST, ov(0.1 * P0))
    x = (-1.1 + math.sqrt(1.1 ** 2 + 4 * 0.9 * 0.1)) / (2 * 0.9)                         # 0.9x^2 + 1.1x - 0.1 = 0
    assert out["delta_eta_u_star"] == pytest.approx(0.5 * x, rel=1e-12)
    assert out["delta_eta_u_star"] == pytest.approx(0.0424990024, rel=1e-8)


def test_hand_substitution_only():
    ref = ref_n2()
    P0 = b.hall_only_state(ref)["P_d_bus_W"]
    out = b.required_utilization_gain(ref, resp(0.0, 1.0), ov(0.05 * P0))
    assert out["status"] == "OK_SUBSTITUTION_ONLY" and out["delta_eta_u_star"] == 0.0
    assert out["delta_s_star"] == pytest.approx(0.05 * 0.5 / (1.0 * 0.3), rel=1e-12)     # w eta_u0 / (chi (1-eta_b))


def test_hand_delivered_ion_cost():
    ref = ref_n2()
    assert b.breakeven_delivered_cost(ref, ADD, 0.05, 0.0) == pytest.approx(300 * 0.5 / (0.7 * 0.55), rel=1e-12)
    assert b.marginal_breakeven_delivered_cost(ref, ADD) == pytest.approx(300 / 0.7, rel=1e-12)           # Pi_H
    assert b.marginal_breakeven_delivered_cost(ref, COST) == pytest.approx(300 / 0.7 * 1.3, rel=1e-12)    # Pi_H(2-eta_b)
    assert b.marginal_breakeven_delivered_cost(ref, resp(0.0, 1.0)) == pytest.approx(300 / 0.7 * 0.3)    # Pi_H(1-eta_b)
    assert b.marginal_breakeven_delivered_cost(ref, resp(0.0, 0.0)) == pytest.approx(0.0, abs=1e-12)     # no benefit
    opt = b.marginal_breakeven_delivered_cost(ref, resp(1.0, 1.0, eta_v_s=1.0))
    assert opt == pytest.approx(300 / 0.7 * (1.3 + 2 * (1 / math.sqrt(0.9) - 1)), rel=1e-12)
    # the payable share of a 300 W/A source with eta_t = 0.9 (C_del = 333.3 W/A): Pi_H eta_u0/(eta_u0 + d) = C_del
    ev = lambda v, u: b.Evidenced(v, u, "assumed", "unit test")
    pe = b.place_evidence(ref, ADD, 0.0, ev(300.0, "W/A"), ev(0.9, "1"), 128)
    assert pe["status"] == "BREAK_EVEN_POSSIBLE"
    assert pe["payable_delta_s"][0] == 0.0
    assert pe["payable_delta_s"][1] == pytest.approx(300 / 0.7 * 0.5 / (300 / 0.9) - 0.5, rel=1e-9)
    assert pe["eta_transport_min"] == pytest.approx(0.7, rel=1e-12)


def test_achievable_share_supply_side():
    ref = ref_n2()                                                     # I_b0 = 1 A, eta_u0 = 0.5
    out = b.achievable_delivered_share(ref, ADD, 60.0, 300.0, 0.5)     # 0.2 A produced, 0.1 A delivered
    assert out["I_source_A"] == pytest.approx(0.2) and out["I_delivered_A"] == pytest.approx(0.1)
    assert out["delta_s"] == pytest.approx(0.05, rel=1e-12)            # 0.1 A / (1 A / 0.5)
    assert out["delivered_cost_W_per_A"] == pytest.approx(600.0)
    assert b.achievable_delivered_share(ref, ADD, 60.0, 300.0, 0.0)["delta_eta_u"] == 0.0   # eta_t -> 0: no gain
    # consistency with the demand side: at the break-even delivered cost the supply equals the requirement
    P0 = b.hall_only_state(ref)["P_d_bus_W"]
    req = b.required_utilization_gain(ref, ADD, ov(0.1 * P0))
    C_del = 0.1 * P0 / (req["delta_s_star"] * ref.mdot_kg_s * N2.coulomb_per_kg)
    sup = b.achievable_delivered_share(ref, ADD, 0.1 * P0, 0.8 * C_del, 0.8)
    assert sup["delta_s"] == pytest.approx(req["delta_s_star"], rel=1e-12)
    with pytest.raises(b.BreakevenInputError):
        b.achievable_delivered_share(ref, ADD, 1e5, 1.0, 1.0)          # beyond the utilization cap
    with pytest.raises(b.BreakevenInputError):
        b.achievable_delivered_share(ref, ADD, 60.0, 300.0, 1.5)


def test_bus_referred_cost_matches_goebel_katz_rf_example():
    # G&K 2008 Sec. 4.5: 230 eV/ion absorbed, rf supply ~90 % efficient -> ~511 W PPU input for a 2 A beam
    c = b.bus_referred_source_cost(230.0, "eV_per_ion", "absorbed", {"generator": 0.9, "coupling": 1.0}, 1.0)
    assert c * 2.0 == pytest.approx(511.1, abs=0.1)
    assert b.bus_referred_source_cost(100.0, "eV_per_ion", "bus", {}, 2.0) == pytest.approx(50.0)
    assert b.bus_referred_source_cost(100.0, "W_per_A", "forward", {"generator": 0.5}, 1.0) == pytest.approx(200.0)


# ---------------------------------------------------------------------------------------------- units and dimensions
def test_thrust_units_match_goebel_katz_xenon_constant():
    # G&K Eq. 2.3-9: T = 1.65 I_b sqrt(V_b) mN for singly charged xenon (gamma = 1)
    ref = b.HallReference(mdot_kg_s=1.0 / XE.coulomb_per_kg, V_d_V=1.0, eta_u=1.0, eta_b=1.0, eta_v=1.0,
                          gamma_div=1.0, eta_ppu_discharge=1.0, mix=XE)
    h = b.hall_only_state(ref)
    assert h["I_b_A"] == pytest.approx(1.0)
    assert h["T_N"] * 1e3 == pytest.approx(1.65, abs=0.005)


def test_hofer_charge_utilization_reduction():
    # one element, singles + doubles: eta_a = gamma^2 eta_v eta_b eta_m eta_q, eta_q from Hofer Eq. 5
    mix = b.IonMix((b.IonSpecies("Xe+", 131.29, 1, 0.9), b.IonSpecies("Xe2+", 131.29, 2, 0.1)))
    eta_q = (0.9 + 0.1 / math.sqrt(2)) ** 2 / (0.9 + 0.1 / 2)
    assert mix.charge_factor == pytest.approx(eta_q, rel=1e-12)
    ref = ref_n2(mix=mix, eta_u=0.8)
    h = b.hall_only_state(ref)
    assert h["eta_a"] == pytest.approx(0.9 ** 2 * 0.9 * 0.7 * 0.8 * eta_q, rel=1e-12)
    assert h["eta_a"] == pytest.approx(h["eta_a_check"], rel=1e-12)            # T^2 / (2 mdot P_d)
    assert mix.mean_charge_per_ion == pytest.approx(1.0 / (0.9 + 0.05))


def test_first_principles_two_population_state():
    # independent recomputation of T and P_d from per-species currents for a mixed Hall beam and N2+ delivered ions
    mixH = b.IonMix((b.IonSpecies("N2+", 28.014, 1, 0.6), b.IonSpecies("N+", 14.007, 1, 0.3),
                     b.IonSpecies("N2++", 28.014, 2, 0.1)))
    ref = ref_n2(mix=mixH, eta_u=0.4, mdot=2e-6, V=250.0)
    r = b.PreionResponse(alpha=0.7, chi=0.4, eta_v_delivered=0.95, mix_delivered=N2)
    d = 0.1
    st = b.arm_state(ref, r, d)
    u_H = 0.4 - 0.3 * d
    I_H = u_H * 2e-6 / sum(f * m * AMU / (z * E_CHARGE) for m, z, f in ((28.014, 1, .6), (14.007, 1, .3), (28.014, 2, .1)))
    I_S = d * 2e-6 / (28.014 * AMU / E_CHARGE)
    V = 250.0
    T = 0.9 * (sum(f * I_H * math.sqrt(2 * m * AMU * 0.9 * V / (z * E_CHARGE))
                   for m, z, f in ((28.014, 1, .6), (14.007, 1, .3), (28.014, 2, .1)))
               + I_S * math.sqrt(2 * 28.014 * AMU * 0.95 * V / E_CHARGE))
    inv_bS = 1 + 0.6 * (1 / 0.7 - 1)
    P = V * (I_H / 0.7 + I_S * inv_bS)
    assert st["eta_a"] == pytest.approx(T * T / (2 * 2e-6 * P), rel=1e-12)
    assert st["eta_u"] == pytest.approx(0.4 + 0.7 * d)


def test_scaling_and_homogeneity():
    ref = ref_n2()
    h = b.hall_only_state(ref)
    h2 = b.hall_only_state(dataclasses.replace(ref, V_d_V=600.0))
    assert h2["Pi_H_bus_W_per_A"] == pytest.approx(2 * h["Pi_H_bus_W_per_A"])     # W/A = V
    assert h2["P_d_W"] == pytest.approx(2 * h["P_d_W"])
    assert h2["T_N"] == pytest.approx(math.sqrt(2) * h["T_N"])
    # scaling mdot and every overhead by k leaves the dimensionless requirement unchanged
    base = b.required_utilization_gain(ref, COST, ov(40.0))
    for k in (0.1, 3.0, 17.0):
        rk = b.required_utilization_gain(dataclasses.replace(ref, mdot_kg_s=k * ref.mdot_kg_s), COST, ov(40.0 * k))
        assert rk["delta_eta_u_star"] == pytest.approx(base["delta_eta_u_star"], rel=1e-12)
    # ion mass per coulomb
    assert N2.kg_per_coulomb / OP.kg_per_coulomb == pytest.approx(28.014 / 15.999)
    # eta_a and the requirement do not depend on eta_v or gamma when S ions share them (same mix)
    for ev_, g in ((0.6, 0.7), (1.0, 1.0)):
        rr = b.required_utilization_gain(ref_n2(eta_v=ev_, gamma=g), resp(1.0, 1.0, eta_v_s=ev_), ov(40.0))
        assert rr["delta_eta_u_star"] == pytest.approx(base["delta_eta_u_star"], rel=1e-12)


# ---------------------------------------------------------------------------------------------- conventions
@pytest.mark.parametrize("alpha,chi,evs", [(1, 0, 0.9), (1, 1, 0.9), (0.6, 0.5, 0.95), (1, 1, 1.0), (0.2, 0.9, 0.9)])
@pytest.mark.parametrize("w", [0.02, 0.1, 0.3])
def test_both_conventions_share_one_breakeven_locus(alpha, chi, evs, w):
    ref = ref_n2(eta_u=0.45, eta_b=0.65, eta_ppu=0.9)
    r = resp(alpha, chi, eta_v_s=evs)
    O = w * b.hall_only_state(ref)["P_d_bus_W"]
    out = b.required_utilization_gain(ref, r, ov(O))
    if out["status"] not in ("OK", "OK_SUBSTITUTION_ONLY"):
        pytest.skip(out["status"])
    d = out["delta_s_star"]
    e = b.evaluate_arm(ref, r, ov(O), d)
    assert abs(e["equal_thrust"]["net_bus_saving_W"]) < 1e-9 * O
    assert abs(e["equal_bus_power"]["thrust_gain_fraction"]) < 1e-9
    assert e["equal_thrust"]["V_d_ratio"] == pytest.approx(e["equal_bus_power"]["V_d_ratio"], rel=1e-9)
    assert e["equal_thrust"]["V_d_ratio"] == pytest.approx(out["V_d_ratio_at_breakeven"], rel=1e-9)
    for dd, sign in ((0.9 * d, -1), (min(1.1 * d, b.delta_s_max(ref, r)), 1)):
        e2 = b.evaluate_arm(ref, r, ov(O), dd)
        assert math.copysign(1, e2["equal_thrust"]["net_bus_saving_W"]) == sign
        assert math.copysign(1, e2["equal_bus_power"]["thrust_gain_fraction"]) == sign
    for conv in ("equal_thrust", "equal_bus_power"):
        assert abs(e[conv]["ledger_residual_W"]) < 1e-9 and abs(e[conv]["eta_a_residual"]) < 1e-12


# ---------------------------------------------------------------------------------------------- monotonicity
def test_monotonicity():
    ref = ref_n2(eta_u=0.5, mdot=1e-6, eta_ppu=0.9)
    prev = -1.0
    for P in (0, 10, 50, 100, 200, 300):                                   # more overhead -> more gain needed
        cur = b.required_utilization_gain(ref, COST, ov(float(P)))["delta_eta_u_star"]
        assert cur > prev or (P == 0 and cur == 0.0)
        prev = cur
    need = [b.required_utilization_gain(dataclasses.replace(ref, V_d_V=V), COST, ov(100.0))["delta_eta_u_star"]
            for V in (150.0, 250.0, 350.0, 450.0)]
    assert all(x > y for x, y in zip(need, need[1:]))                     # higher V_d -> larger P_d0 -> less needed
    need = [b.required_utilization_gain(dataclasses.replace(ref, mdot_kg_s=m), COST, ov(100.0))["delta_eta_u_star"]
            for m in (0.8e-6, 1.6e-6, 3.2e-6)]
    assert all(x > y for x, y in zip(need, need[1:]))                     # more flow -> larger P_d0 -> less needed
    light = b.required_utilization_gain(ref_n2(mix=OP, mdot=1e-6), resp(1, 1, mix=OP), ov(100.0))
    heavy = b.required_utilization_gain(ref_n2(mix=XE, mdot=1e-6), resp(1, 1, mix=XE), ov(100.0))
    assert heavy["delta_eta_u_star"] > light["delta_eta_u_star"]          # fewer ions per kg -> harder
    for w in (0.05, 0.2):                                                 # cost offset never needs more than add-only
        O = w * b.hall_only_state(ref)["P_d_bus_W"]
        assert (b.required_utilization_gain(ref, COST, ov(O))["delta_eta_u_star"]
                < b.required_utilization_gain(ref, ADD, ov(O))["delta_eta_u_star"])
    c = [b.breakeven_delivered_cost(ref, r, d, 0.0) for r in (ADD, COST) for d in (0.01, 0.1, 0.3)]
    assert c[0] > c[1] > c[2] and c[3] > c[4] > c[5]                      # break-even ion cost falls with share


def test_optimistic_corner_dominates_the_declared_box():
    ref = ref_n2(eta_u=0.4, eta_b=0.6, eta_v=0.85)
    corner = b.supremum_breakeven_delivered_cost(ref, resp(1.0, 1.0, eta_v_s=1.0), 0.0, 64)["sup_W_per_A"]
    for a in (0.0, 0.5, 1.0):
        for c in (0.0, 0.5, 1.0):
            for evs in (0.85, 0.95, 1.0):
                s = b.supremum_breakeven_delivered_cost(ref, resp(a, c, eta_v_s=evs), 0.0, 64)["sup_W_per_A"]
                assert s <= corner * (1 + 1e-12)


def test_fixed_overhead_lowers_the_payable_cost():
    ref = ref_n2()
    s0 = b.supremum_breakeven_delivered_cost(ref, COST, 0.0, 128)
    s1 = b.supremum_breakeven_delivered_cost(ref, COST, 20.0, 128)
    assert s0["attained_in_limit"] and not s1["attained_in_limit"]
    assert s1["sup_W_per_A"] < s0["sup_W_per_A"] and s1["argmax_delta_s"] > 0.0


# ---------------------------------------------------------------------------------------------- ledgers and contract
def test_overhead_from_ledgers_and_ecr_magnet():
    hall = {k: 1.0 for k in b.COMMON_COMPONENTS}
    arm = dict(hall, ecr_source=80.0, ecr_magnet=15.0, thermal_control=4.0)
    o = b.overhead_from_ledgers("ecr_hall", arm, hall, 3.0, 2.0)
    assert o.total_W == pytest.approx(80 + 15 + 3 + 3 + 2)
    assert o.generator_W == 80.0 and o.fixed_W == pytest.approx(23.0)
    with pytest.raises(b.BreakevenInputError):
        b.overhead_from_ledgers("rf_hall", arm, hall, 0.0, 0.0)          # ECR components in an RF ledger


def test_boundary_contract_is_lazy_and_explicit(monkeypatch):
    monkeypatch.setitem(sys.modules, "abep_sim.arch_boundary", None)     # simulate absence
    with pytest.raises(b.BreakevenContractError, match="not present"):
        b.check_boundary_contract()
    fake = types.ModuleType("abep_sim.arch_boundary")                     # stand-in; the real module is not required
    fake.BOUNDARY_VERSION = "bus_power_boundary_v1"
    fake.COMMON_COMPONENTS = b.COMMON_COMPONENTS
    fake.PREIONIZER_COMPONENTS = {"hall_only": (), **b.SOURCE_COMPONENTS}
    monkeypatch.setitem(sys.modules, "abep_sim.arch_boundary", fake)
    assert b.check_boundary_contract()["components_checked"]
    fake.PREIONIZER_COMPONENTS = {"hall_only": (), "rf_hall": ("rf_source",), "ecr_hall": ("ecr_source",)}
    with pytest.raises(b.BreakevenContractError, match="ecr_hall"):
        b.check_boundary_contract()
    fake.BOUNDARY_VERSION = "bus_power_boundary_v2"
    with pytest.raises(b.BreakevenContractError, match="expected"):
        b.check_boundary_contract()


def test_overhead_from_v1_format_ledgers():
    def ledger(arch, bus):
        return {"boundary_version": "bus_power_boundary_v1", "architecture": arch, "P_bus_W": sum(bus.values()),
                "items": [{"component": k, "P_load_W": v, "efficiency": 1.0, "P_bus_W": v, "P_loss_W": 0.0}
                          for k, v in bus.items()], "residual_W": 0.0}
    hall = {k: 2.0 for k in b.COMMON_COMPONENTS}
    arm = dict(hall, rf_source=120.0, housekeeping=5.0)
    o = b.overhead_from_boundary_ledgers(ledger("rf_hall", arm), ledger("hall_only", hall))
    assert o.arch == "rf_hall" and o.total_W == pytest.approx(123.0) and o.boundary_v1_conformant
    bad = ledger("rf_hall", arm)
    bad["boundary_version"] = "bus_power_boundary_v0"
    with pytest.raises(b.BreakevenInputError):
        b.overhead_from_boundary_ledgers(bad, ledger("hall_only", hall))
    with pytest.raises(b.BreakevenInputError):
        b.overhead_from_boundary_ledgers(ledger("rf_hall", arm), ledger("rf_hall", arm))
    assert not b.BusOverhead(arch="rf_hall", source_bus_W={"rf_source": 1.0}, delta_common_bus_W=ZERO_COMMON,
                             interstage_loss_bus_W=3.0, extra_ppu_bus_W=0.0).boundary_v1_conformant


def test_mass_breakeven_hand():
    ev = lambda v, u: b.Evidenced(v, u, "assumed", "unit test")
    hw = {"source_head": ev(0.3, "kg"), "source_generator_ppu": ev(0.4, "kg"), "source_magnets": ev(0.2, "kg"),
          "interstage": ev(0.1, "kg"), "thermal_added": ev(0.0, "kg")}
    out = b.mass_breakeven("rf_hall", "equal_thrust", ev(100.0, "W"), ev(0.01, "kg/W"), ev(0.0, "kg"), hw)
    assert out["net_mass_benefit_kg"] == pytest.approx(0.0, abs=1e-12) and out["breaks_even"]
    assert out["required_benefit"] == pytest.approx(100.0)
    out = b.mass_breakeven("ecr_hall", "equal_bus_power", ev(0.002, "N"), ev(200.0, "kg/N"), ev(-0.1, "kg"), hw)
    assert out["net_mass_benefit_kg"] == pytest.approx(0.4 + 0.1 - 1.0)
    with pytest.raises(b.BreakevenInputError):
        b.mass_breakeven("rf_hall", "equal_thrust", ev(1.0, "N"), ev(0.01, "kg/W"), ev(0.0, "kg"), hw)


def test_life_breakeven_hand():
    ev = lambda v, u: b.Evidenced(v, u, "assumed", "unit test")
    ratio = b.hall_erosion_life_ratio(2.0, 0.5, 1.0, 0.5)
    assert ratio == pytest.approx(2.0)
    out = b.life_breakeven(ev(15000.0, "h"), ev(1.5, "1"),
                           {"hall_channel_erosion": ev(20000.0, "h"), "cathode": ev(30000.0, "h")},
                           {"hall_channel_erosion": ev(40000.0, "h"), "cathode": ev(30000.0, "h"),
                            "rf_window": ev(18000.0, "h")}, ["rf_window"])
    assert out["life_hall_only_h"] == 20000.0 and out["life_arm_h"] == 18000.0
    assert out["source_limited"] and not out["life_breaks_even"]
    assert out["classification"] == "ARM_WORSE_SOURCE_LIMITED"
    assert out["required_life_h"] == 22500.0 and not out["requirement_met_arm"]
    assert out["common_hardware_life_change_h"]["hall_channel_erosion"] == 20000.0


# ---------------------------------------------------------------------------------------------- refusal paths
def test_no_defaults_anywhere():
    for name, obj in inspect.getmembers(b):
        if inspect.isfunction(obj) and obj.__module__ == b.__name__ and not name.startswith("_"):
            defaults = [p for p in inspect.signature(obj).parameters.values() if p.default is not p.empty]
            assert not defaults, f"{name} has defaults {defaults}"
        if dataclasses.is_dataclass(obj) and obj.__module__ == b.__name__:
            for f in dataclasses.fields(obj):
                assert f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING, (name, f.name)


@pytest.mark.parametrize("field,value", [("mdot_kg_s", None), ("mdot_kg_s", -1e-6), ("V_d_V", float("nan")),
                                         ("eta_u", 1.2), ("eta_b", 0.0), ("eta_v", True), ("gamma_div", "0.9"),
                                         ("eta_ppu_discharge", float("inf"))])
def test_refuses_invalid_hall_reference(field, value):
    kw = dict(mdot_kg_s=1e-6, V_d_V=300.0, eta_u=0.5, eta_b=0.7, eta_v=0.9, gamma_div=0.9, eta_ppu_discharge=0.9,
              mix=N2)
    kw[field] = value
    with pytest.raises(b.BreakevenInputError):
        b.HallReference(**kw)


def test_refusal_paths():
    E = b.BreakevenInputError
    with pytest.raises(E):
        b.IonMix((b.IonSpecies("N2+", 28.014, 1, 0.6),))                              # fractions != 1
    with pytest.raises(E):
        b.IonSpecies("N2+", 28.014, 0, 1.0)                                            # charge < 1
    with pytest.raises(E):
        b.PreionResponse(alpha=1.2, chi=0.0, eta_v_delivered=0.9, mix_delivered=N2)
    with pytest.raises(E):
        b.BusOverhead(arch="hall_only", source_bus_W={}, delta_common_bus_W=ZERO_COMMON, interstage_loss_bus_W=0.0,
                      extra_ppu_bus_W=0.0)
    with pytest.raises(E):
        b.BusOverhead(arch="rf_hall", source_bus_W={"ecr_source": 1.0}, delta_common_bus_W=ZERO_COMMON,
                      interstage_loss_bus_W=0.0, extra_ppu_bus_W=0.0)
    partial = dict(ZERO_COMMON)
    partial.pop("thermal_control")
    with pytest.raises(E):
        b.BusOverhead(arch="rf_hall", source_bus_W={"rf_source": 1.0}, delta_common_bus_W=partial,
                      interstage_loss_bus_W=0.0, extra_ppu_bus_W=0.0)
    with pytest.raises(E):
        b.BusOverhead(arch="ecr_hall", source_bus_W={"ecr_source": 1.0}, delta_common_bus_W=ZERO_COMMON,
                      interstage_loss_bus_W=0.0, extra_ppu_bus_W=0.0)                  # ecr_magnet omitted
    with pytest.raises(E):
        b.BusOverhead(arch="rf_hall", source_bus_W={"rf_source": 1.0}, delta_common_bus_W=ZERO_COMMON,
                      interstage_loss_bus_W=None, extra_ppu_bus_W=0.0)
    with pytest.raises(E):
        b.arm_state(ref_n2(), ADD, 0.6)                                                # beyond eta_u <= 1
    with pytest.raises(E):
        b.breakeven_delivered_cost(ref_n2(), ADD, 0.0, 0.0)
    with pytest.raises(E):
        b.Evidenced(1.0, "W/A", "TBD", "requires a measurement")                        # TBD cannot be evaluated
    with pytest.raises(E):
        b.Evidenced(1.0, "W/A", "measured", "")
    ev = lambda v, u: b.Evidenced(v, u, "assumed", "unit test")
    with pytest.raises(E):
        b.place_evidence(ref_n2(), ADD, 0.0, ev(100.0, "eV/ion"), ev(0.5, "1"), 64)     # wrong unit
    with pytest.raises(E):
        b.place_evidence(ref_n2(), ADD, 0.0, 100.0, ev(0.5, "1"), 64)                   # untagged value
    with pytest.raises(E):
        b.supremum_breakeven_delivered_cost(ref_n2(), ADD, 0.0, 4)
    with pytest.raises(E):
        b.bus_referred_source_cost(230.0, "eV_per_ion", "absorbed", {"generator": 0.9}, 1.0)   # coupling missing
    with pytest.raises(E):
        b.bus_referred_source_cost(230.0, "eV/ion", "bus", {}, 1.0)
    with pytest.raises(E):
        b.mass_breakeven("rf_hall", "equal_thrust", ev(1.0, "W"), ev(0.01, "kg/W"), ev(0.0, "kg"),
                         {"source_head": ev(1.0, "kg")})
    with pytest.raises(E):
        b.life_breakeven(ev(15000.0, "h"), ev(1.5, "1"), {"cathode": ev(1.0, "h")},
                         {"cathode": ev(1.0, "h")}, ["cathode"])                           # overlapping mechanism
    with pytest.raises(E):
        b.life_breakeven(ev(15000.0, "h"), ev(0.5, "1"), {"cathode": ev(1.0, "h")},
                         {"cathode": ev(1.0, "h"), "x": ev(1.0, "h")}, ["x"])              # qualification factor < 1
    with pytest.raises(E):
        b.required_utilization_gain(ref_n2(), ADD, 50.0)                                 # overhead must be a ledger


# ---------------------------------------------------------------------------------------------- committed surfaces
def test_committed_surfaces_match_module_and_pass_self_checks():
    import hashlib
    import json
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "docs", "architecture_comparison", "breakeven", "breakeven_surfaces_v1.json")
    doc = json.load(open(path))
    with open(os.path.join(root, "abep_sim", "breakeven.py"), "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    assert doc["provenance"]["module_sha256"] == sha, "rebuild: python scripts/architecture/build_breakeven_surfaces.py"
    assert doc["self_checks"]["all_pass"]
    assert doc["breakeven_version"] == b.BREAKEVEN_VERSION and doc["boundary"]["version"] == b.BOUNDARY_VERSION
    assert "winner" not in json.dumps(doc).lower()
