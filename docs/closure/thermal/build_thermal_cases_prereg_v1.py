"""Builder of the P7 thermal-closure case preregistration (A9.38 priority 7, lane L-THERMAL).

Writes, byte-deterministically (sorted keys, indent 1, trailing newline):
  docs/closure/thermal/thermal_cases_prereg_v1.json   case definitions + method (the preregistration)
  docs/closure/thermal/thermal_load_inputs_v1.json    registered load inputs v1 (re-run inputs; versioned)
  docs/closure/thermal/thermal_cases_prereg_lock_v1.json   sha256 lock of both

Every number is either copied from a sha256-pinned repository record (cited by path + pointer) or a selected
engineering assumption with an evidence class, an uncertainty and, where it is a memory value, the word "verify".
Derived numbers (areas, conductances, view factors) are computed here from the registered primitives; the derivation
is the code below and is restated in each entry. Docs tooling only: no simulator code imports this file.
"""

import hashlib
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def sha(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def src(path, pointer=None, note=None):
    d = {"path": path, "sha256": sha(path)}
    if pointer:
        d["pointer"] = pointer
    if note:
        d["note"] = note
    return d


def r9(x):
    """Derived floats are written at full precision (shortest round-trip repr): view-factor summation and reciprocity
    are checked by the model at 1e-9, so no rounding is applied."""
    return float(x)


PI = math.pi

# ------------------------------------------------------------------------------------------------ sources
S_DBF1 = "docs/baseline/DBF-1/dbf1_v1.json"
S_DBF1_LOCK = "docs/baseline/DBF-1/dbf1_lock_v1.json"
S_A938 = "docs/decisions/OD_2026_10_08_A9_38_ARCHITECTURE_FROZEN_DESIGN_CLOSURE_PROGRAMME.md"
S_A937 = "docs/decisions/OD_2026_10_08_A9_37_DBF_1_DESIGN_BASELINE_FREEZE.md"
S_NPT2 = "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/prereg_v2.json"
S_NPT2_LOCK = "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/prereg_lock_v2.json"
S_NPT_VER = "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/verification_report_model_v2_v2.json"
S_H25 = "docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json"
S_H21 = "docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json"
S_H24 = "docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json"
S_H1F = "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json"
S_LIM = "schemas/thermal_life/limits_v1.json"
S_P4 = "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json"
S_P3 = "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json"
S_P1 = "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json"
S_MCQ = "docs/experiments/magnet_coil/magnet_coil_qualification_v1.json"
S_A907 = "docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json"
S_DS2 = "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json"
S_MP5 = "docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json"
S_GATES = "config/assessment/gate_thresholds_v1.json"
S_OWN147 = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
S_A914 = "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json"
S_CONST = "crates/abep-types/src/constants.rs"
S_PROP = "crates/abep-mission/src/propagation.rs"
S_BOARD = "docs/closure/closure_board_v1.json"
S_MATG = "docs/closure/materials/materials_gates_v1.json"

ASSUMED = "assumed"
ANALOG = "published analog"
MODEL = "model-derived"
MEASURED = "measured"
INFERRED = "inferred"

# ------------------------------------------------------------------------------------------------ geometry primitives
# DBF-1 G-RP1 channel (DBF1-H1-01..04) and the H2-1 RP-1 'worst-case assumptions' magnetic-circuit case: the only H2-1
# case sized at the DBF1-BZ-05 MC-1 field capability (403 G), so its wall thickness, coil build and envelope are used
# together (one consistent case); the core is solid (H1F-MC-04, no cathode bore).
r_in = 0.029
r_out = 0.041
L_ch = 0.1032
t_w = 0.006
build_ci = 0.006826
clear = 0.0005
L_coil = 0.08256
r_body = 0.063
t_shell = 0.003
t_bp = 0.005
L_body = 0.1082
L_core = 0.11
r_wi_bk = r_in - t_w  # 0.023
r_ci_o = r_wi_bk - clear  # 0.0225
r_core = r_ci_o - build_ci  # 0.015674
r_wo_bk = r_out + t_w  # 0.047
r_co_i = r_wo_bk + 0.0015  # 0.0485
r_shell_i = r_body - t_shell  # 0.060

# ICP (DBF1-ICP-02 / -04) + assumed construction thicknesses
L_so = 0.05
r_ap = 0.06
r_mod = 0.09
L_mod = 0.15
L_col = 0.10
t_tube = 0.003
t_hous = 0.003
t_col = 0.001
ant_turns = 3
ant_d = 0.006
ant_wall = 0.001
r_ant = 0.075

# ------------------------------------------------------------------------------------------------ material properties
H_C = 0.5 * (155.0 + 3100.0)  # H25-30 midpoint (H2-5 nominal convention: range midpoint): bolted / clamped joints
H_C_COIL = 155.0  # H25-30 lower end: unpotted porous ceramic-insulated winding (MCQ-EM-03) on iron in vacuum
K_BN = 29.0  # Martinez 2014 M26 (H25-24 note)
K_BN_TMULT = 0.75  # H25-45 midpoint
F_LEN = 0.75  # H25-44 midpoint
W_SUP = 0.0035  # H25-21 midpoint
K_HIPERCO = 29.8
ARMCO_T = [273.15, 473.15, 673.15, 873.15, 913.15, 973.15, 1023.15]
ARMCO_K = [74.2, 62.0, 49.5, 39.1, 37.1, 34.63, 32.5]
GRADE = 0.5 * (0.8 + 1.02)  # H25-25 midpoint
EPS_BN = 0.92
EPS_METAL = 0.5 * (0.14 + 0.38)  # H25-27 midpoint
EPS_ANODE = 0.5 * (0.14 + 0.8)  # H25-28 midpoint
EPS_Z93, ALPHA_Z93 = 0.92, 0.17  # H25-29 z93_white_inorganic
EPS_GLASS = 0.85
EPS_COPPER = 0.14  # lowest registered metal emittance (H25-27 lower end), used for the antenna conductor
EPS_COLLECTOR = EPS_ANODE

# ------------------------------------------------------------------------------------------------ derived geometry
A_an = PI * (r_out**2 - r_in**2)
A_wi_ch = 2 * PI * r_in * L_ch
A_wo_ch = 2 * PI * r_out * L_ch
A_wi_bk = 2 * PI * r_wi_bk * L_ch
A_wo_bk = 2 * PI * r_wo_bk * L_ch
A_ci = 2 * PI * r_ci_o * L_coil
A_co = 2 * PI * r_co_i * L_coil
A_pi_cav = A_wi_bk - A_ci
A_po_cav = A_wo_bk - A_co
A_pi_fr = PI * r_wi_bk**2
A_po_fr = PI * (r_body**2 - r_wo_bk**2)
A_po_lat = 2 * PI * r_body * L_body
A_icp_up = PI * (r_mod**2 - r_ap**2)
A_ho_out = 2 * PI * r_mod * L_mod
A_ho_dn = A_icp_up
A_ho_in = 2 * PI * (r_mod - t_hous) * L_mod
A_ve_out = 2 * PI * (r_ap + t_tube) * L_mod
ant_len = ant_turns * 2 * PI * r_ant
A_ant = PI * ant_d * ant_len
A_ve_bore = 2 * PI * r_ap * (L_mod - L_col)
A_col = 2 * PI * r_ap * L_col
A_mo = 0.01
A_ma = 0.02

# volumes / masses
V_an_t = 0.010
V_an = A_an * V_an_t
V_wi = PI * (r_in**2 - r_wi_bk**2) * L_ch
V_wo = PI * (r_wo_bk**2 - r_out**2) * L_ch
V_pi = PI * r_core**2 * L_core + PI * r_wi_bk**2 * t_bp
V_po = PI * (r_body**2 - r_shell_i**2) * L_body + PI * (r_body**2 - r_wo_bk**2) * t_bp
V_bp = PI * r_body**2 * t_bp
RHO_IN600, RHO_HIPERCO, RHO_IRON, RHO_BNS, RHO_CU, RHO_GLASS, RHO_AL, RHO_TI = (
    8470.0, 8110.0, 7860.0, 2000.0, 8960.0, 2230.0, 2700.0, 4430.0)
m_an = RHO_IN600 * V_an
m_wi = RHO_BNS * V_wi
m_wo = RHO_BNS * V_wo
m_pi = RHO_HIPERCO * V_pi
m_po = RHO_IRON * V_po
m_bp = RHO_IRON * V_bp
m_ci = 0.2765
m_co = 1.243
m_ct = 0.05
V_ve = PI * ((r_ap + t_tube) ** 2 - r_ap**2) * L_mod
m_ve = RHO_GLASS * V_ve
V_ant = PI * ((ant_d / 2) ** 2 - (ant_d / 2 - ant_wall) ** 2) * ant_len
m_ant = RHO_CU * V_ant
V_col = 2 * PI * (r_ap - t_col / 2) * t_col * L_col
m_col = RHO_IN600 * V_col
V_ho = PI * (r_mod**2 - (r_mod - t_hous) ** 2) * L_mod + 2 * PI * (r_mod**2 - (r_ap + t_tube) ** 2) * t_hous
m_ho = RHO_AL * V_ho
m_ma = 0.8
m_mo = 0.3
RH_AREAL = 4.0  # kg/m^2 (assumed)

# conductances
G_wi = 1.0 / (F_LEN * L_ch / (K_BN * K_BN_TMULT * 2 * PI * (r_in - t_w / 2) * t_w) + 1.0 / (H_C * PI * 2 * (r_in - t_w / 2) * W_SUP))
G_wo = 1.0 / (F_LEN * L_ch / (K_BN * K_BN_TMULT * 2 * PI * (r_out + t_w / 2) * t_w) + 1.0 / (H_C * PI * 2 * (r_out + t_w / 2) * W_SUP))
A_core = PI * r_core**2
L_core_eff = L_core + K_HIPERCO / H_C
A_shell = PI * (r_body**2 - r_shell_i**2)
K_ARMCO_REF = 49.5 * GRADE  # at 673.15 K, for the folded joint term only
L_shell_eff = L_body + K_ARMCO_REF / H_C
A_c_ci = 2 * PI * r_core * L_coil
A_c_co = 2 * PI * r_shell_i * L_coil
A_c_ct = 0.002



def g_wall(r_m, h):
    return 1.0 / (F_LEN * L_ch / (K_BN * K_BN_TMULT * 2 * PI * r_m * t_w) + 1.0 / (h * PI * 2 * r_m * W_SUP))


SENS_OVERRIDES = {
    "SENS-WALL-LO": {"inputs": {"discharge.f_walls_hot": 0.0439}},
    "SENS-ANODE-LO": {"inputs": {"discharge.f_anode_hot": 0.0206}},
    "SENS-CORE-ARMCO": {"links": {"L_PI_BP": {"k_record_id": "MAT.armco.k", "length_m": L_core + K_ARMCO_REF / H_C}}},
    "SENS-HC-LO": {"links": {"L_PI_BP": {"length_m": L_core + K_HIPERCO / 155.0}, "L_PO_BP": {"length_m": L_body + K_ARMCO_REF / 155.0},
                             "L_WI_BP": {"G_W_K": g_wall(r_in - t_w / 2, 155.0)}, "L_WO_BP": {"G_W_K": g_wall(r_out + t_w / 2, 155.0)}}},
    "SENS-HC-HI": {"links": {"L_PI_BP": {"length_m": L_core + K_HIPERCO / 3100.0}, "L_PO_BP": {"length_m": L_body + K_ARMCO_REF / 3100.0},
                             "L_WI_BP": {"G_W_K": g_wall(r_in - t_w / 2, 3100.0)}, "L_WO_BP": {"G_W_K": g_wall(r_out + t_w / 2, 3100.0)},
                             "L_CI_PI": {"h_c_W_m2K": 3100.0}, "L_CO_PO": {"h_c_W_m2K": 3100.0}, "L_CT_BP": {"h_c_W_m2K": 3100.0}}},
    "SENS-GAN-LO": {"links": {"L_AN_BP": {"G_W_K": 0.55}}},
    "SENS-COIL-CAP": {"inputs": {"coils.hot_inner_W": 27.84, "coils.hot_outer_W": 58.4}},
    "SENS-RETURN-HI": {"inputs": {"discharge.E_return_hot_V": 93.8}},
    "SENS-TSC-20": {"T_SC_K": 293.15},
    "SENS-TSC-40": {"T_SC_K": 313.15},
}

# ------------------------------------------------------------------------------------------------ view factors
F_an_exit = (math.sqrt(L_ch**2 + (r_out - r_in) ** 2) - L_ch) / (r_out - r_in)
F_an_w = 0.5 * (1.0 - F_an_exit)
F_wi_an = A_an * F_an_w / A_wi_ch
F_wo_an = A_an * F_an_w / A_wo_ch
F_wi_exit = F_wi_an
F_wo_exit = F_wo_an
F_wi_wo = 1.0 - 2.0 * F_wi_an
F_wo_wi = A_wi_ch * F_wi_wo / A_wo_ch
F_wo_wo = 1.0 - 2.0 * F_wo_an - F_wo_wi
# P3 radiative-view parametric study, nearest registered grid row to DBF-1 (L/Ro 1.22 -> 1.0, rap/Ro 1.46 -> 1.5,
# wall/Ro 0.73 -> 0.6, H/Ro 3.66 -> 3.0, tau 0)
P3_ROW = {"aperture": 0.6509, "PI_face": 0.6816, "PO_face": 0.5713, "PO_lateral": 0.008301}
up_af = {
    "S_AN": A_an * F_an_exit * P3_ROW["aperture"],
    "S_WI_CH": A_wi_ch * F_wi_exit * P3_ROW["aperture"],
    "S_WO_CH": A_wo_ch * F_wo_exit * P3_ROW["aperture"],
    "S_PI_FR": A_pi_fr * P3_ROW["PI_face"],
    "S_PO_FR": A_po_fr * P3_ROW["PO_face"],
    "S_PO_LAT": A_po_lat * P3_ROW["PO_lateral"],
}
# bore: Howell C-40 coaxial discs of radius r_ap separated by L_mod
rr = r_ap / L_mod
XX = 1 + (1 + rr * rr) / (rr * rr)
F_dd = 0.5 * (XX - math.sqrt(XX * XX - 4))
A_bore_disc = PI * r_ap**2
A_bore_cyl = 2 * PI * r_ap * L_mod
F_cyl_end = A_bore_disc * (1 - F_dd) / A_bore_cyl
F_cyl_cyl = 1 - 2 * F_cyl_end


def ext_rows():
    ex = P3_ROW["aperture"]
    rows = {
        "S_AN": {"S_AN": 0.0, "S_WI_CH": F_an_w, "S_WO_CH": F_an_w, "S_ICP_UP": F_an_exit * ex},
        "S_WI_CH": {"S_AN": F_wi_an, "S_WI_CH": 0.0, "S_WO_CH": F_wi_wo, "S_ICP_UP": F_wi_exit * ex},
        "S_WO_CH": {"S_AN": F_wo_an, "S_WI_CH": F_wo_wi, "S_WO_CH": F_wo_wo, "S_ICP_UP": F_wo_exit * ex},
        "S_PI_FR": {"S_ICP_UP": P3_ROW["PI_face"]},
        "S_PO_FR": {"S_ICP_UP": P3_ROW["PO_face"]},
        "S_PO_LAT": {"S_ICP_UP": P3_ROW["PO_lateral"]},
    }
    rows["S_ICP_UP"] = {k: v / A_icp_up for k, v in up_af.items()}
    return rows


# ------------------------------------------------------------------------------------------------ records
def num(value, units, source, ec, uncertainty, note=None):
    d = {"value": r9(value) if isinstance(value, float) else value, "units": units, "source": source,
         "evidence_class": ec, "uncertainty": uncertainty}
    if note:
        d["note"] = note
    return d


def material(quantity, form, tmin, tmax, source, ec, uncertainty, validation="NOT_VALIDATED"):
    return {"quantity": quantity, "form": form, "T_min_K": tmin, "T_max_K": tmax, "source": source,
            "evidence_class": ec, "uncertainty": uncertainty, "validation_status": validation}


def const(v):
    return {"form": "CONSTANT", "value": r9(v)}


def table(ts, vs):
    return {"form": "PIECEWISE_LINEAR", "T_K": [r9(t) for t in ts], "values": [r9(v) for v in vs]}


TLO, THI = 100.0, 1500.0
in600_cp = table([TLO, 293.15, 773.15, 1073.15, THI], [444.0, 444.0, 536.0, 611.0, 611.0])
in600_k = table([TLO, 373.15, 773.15, 1073.15, THI], [15.9, 15.9, 22.1, 27.5, 27.5])
armco_k = table([TLO] + ARMCO_T + [THI], [a * GRADE for a in [ARMCO_K[0]] + ARMCO_K + [ARMCO_K[-1]]])

MATERIALS = {
    "MAT.in600.cp": material("specific_heat", in600_cp, TLO, THI,
                             "INCONEL 600 c_p 444 / 536 / 611 J/(kg K) at 20 / 500 / 800 degC (SMC datasheet rows cited by P4 PR-012..PR-017, " + S_P4 + " /property_records); held constant outside 20-800 degC (assumed)",
                             MEASURED, "typical datasheet values; constant extension outside the table (assumed)"),
    "MAT.in600.k": material("thermal_conductivity", in600_k, TLO, THI,
                            "INCONEL 600 k 15.9 / 22.1 / 27.5 W/(m K) at 100 / 500 / 800 degC (P4 PR-015..PR-017, " + S_P4 + "); held constant outside the table (assumed)",
                            MEASURED, "typical datasheet values; constant extension (assumed)"),
    "MAT.bns.cp": material("specific_heat", const(800.0), TLO, THI, "BN-SiO2 c_p 800 J/(kg K): handbook-class value from memory (verify)", ASSUMED, "+/- 25 % (verify)"),
    "MAT.bns.k": material("thermal_conductivity", const(K_BN * K_BN_TMULT), TLO, THI,
                          "BN-SiO2 (M26) 29 W/(m K) (EXT-MARTINEZ2014 via H2-5 H25-24 note) x H25-45 midpoint 0.75 temperature allowance; " + S_H25,
                          INFERRED, "H25-24 grade span 10-75 W/(m K); H25-45 0.5-1.0"),
    "MAT.hiperco.cp": material("specific_heat", const(420.0), TLO, THI, "FeCo-2V (Hiperco 50) c_p 420 J/(kg K) from memory (verify)", ASSUMED, "+/- 15 % (verify)"),
    "MAT.hiperco.k": material("thermal_conductivity", const(K_HIPERCO), TLO, THI,
                              "FeCo-2V (Hiperco 50) k 29.8 W/(m K): supplier datasheet value from memory (verify; the H2-1 SRC-HIPERCO50 record in " + S_H21 + " carries no k); lower than the Armco iron table, used for the inner core (H1F-MA-01)",
                              ASSUMED, "+/- 20 % (verify)"),
    "MAT.armco.cp": material("specific_heat", const(450.0), TLO, THI, "pure iron c_p 450 J/(kg K) from memory (verify)", ASSUMED, "+/- 15 % (verify)"),
    "MAT.armco.k": material("thermal_conductivity", armco_k, TLO, THI,
                            "Armco iron k(T) EXT-NBS-ARMCO1967 Table 2 (273.15-913.15 K measured; 973.15 / 1023.15 K Lorenz-function continuation) as transcribed in " + S_H25 + " /material_properties, x grade multiplier 0.91 (H25-25 midpoint); held constant below 273.15 K and above 1023.15 K (assumed)",
                            MEASURED, "source k error <= 2 %; grade multiplier 0.8-1.02 (H25-25); constant extensions assumed"),
    "MAT.cu.cp": material("specific_heat", const(385.0), TLO, THI, "copper c_p 385 J/(kg K) from memory (verify)", ASSUMED, "+/- 10 % (verify)"),
    "MAT.cu.k": material("thermal_conductivity", const(396.9), TLO, THI,
                         "OFHC copper k 396.9 W/(m K) at 293.15 K (EXT-NIST-CRYO, " + S_H25 + " /material_properties); along-conductor value, held constant (assumed); the radial winding-pack value is lower (verify)",
                         MEASURED, "constant extension above 300 K assumed"),
    "MAT.glass.cp": material("specific_heat", const(750.0), TLO, THI, "borosilicate glass c_p 750 J/(kg K) from memory (verify)", ASSUMED, "+/- 15 % (verify)"),
    "MAT.glass.k": material("thermal_conductivity", const(1.13), TLO, THI, "borosilicate glass k 1.13 W/(m K) from memory (verify)", ASSUMED, "+/- 15 % (verify)"),
    "MAT.al.cp": material("specific_heat", const(900.0), TLO, THI, "aluminium alloy c_p 900 J/(kg K) from memory (verify)", ASSUMED, "+/- 10 % (verify)"),
    "MAT.al.k": material("thermal_conductivity", const(154.37), TLO, THI,
                         "Al 6061-T6 k 154.37 W/(m K) at 293.15 K (EXT-NIST-CRYO, " + S_H25 + " /material_properties), held constant (assumed)",
                         MEASURED, "constant extension above 300 K assumed"),
    "MAT.ti.cp": material("specific_heat", const(520.0), TLO, THI, "Ti-6Al-4V c_p 520 J/(kg K) from memory (verify)", ASSUMED, "+/- 10 % (verify)"),
    "MAT.ti.k": material("thermal_conductivity", const(7.37), TLO, THI,
                         "Ti-6Al-4V k 7.37 W/(m K) at 293.15 K (EXT-NIST-CRYO, " + S_H25 + " /material_properties), held constant (assumed)",
                         MEASURED, "constant extension above 300 K assumed"),
    "MAT.box.cp": material("specific_heat", const(900.0), TLO, THI, "match enclosure (aluminium) c_p 900 J/(kg K) from memory (verify)", ASSUMED, "+/- 20 % (verify)"),
}
OPTICS = {
    "OPT.bns.eps": material("emittance_IR", const(EPS_BN), TLO, THI, "BN-SiO2 0.92 (EXT-MAZOUFFRE2005 p. 4 8-9 um band; H2-5 H25-26, " + S_H25 + "), used as total hemispherical (verify)", ANALOG, "band value as total (verify)"),
    "OPT.metal.eps": material("emittance_IR", const(EPS_METAL), TLO, THI, "internal metal 0.26 = midpoint of 0.14-0.38 (EXT-HENNINGER1984 machined / sandblasted stainless; H2-5 H25-27)", ANALOG, "0.14-0.38"),
    "OPT.anode.eps": material("emittance_IR", const(EPS_ANODE), TLO, THI, "anode 0.47 = midpoint of 0.14-0.8 (H2-5 H25-28)", ANALOG, "0.14-0.8"),
    "OPT.z93.eps": material("emittance_IR", const(EPS_Z93), TLO, THI, "Z-93 class white inorganic 0.92 (EXT-HENNINGER1984 white-paint table; H2-5 H25-29); owner row 84 requires a high-emittance temperature-capable exterior coating (H1F-MC-10); coating temperature capability TBD (H1F-MA-06)", ANALOG, "room-temperature value; coating capability not established"),
    "OPT.z93.alpha": material("absorptance_solar", const(ALPHA_Z93), TLO, THI, "Z-93 class white inorganic 0.17 (EXT-HENNINGER1984; H2-5 H25-29); beginning of life", ANALOG, "BOL; degradation not modelled (verify)"),
    "OPT.glass.eps": material("emittance_IR", const(EPS_GLASS), TLO, THI, "borosilicate glass 0.85 from memory (verify); P3-R-03 dielectric emittance TBD", ASSUMED, "+/- 0.1 (verify)"),
    "OPT.copper.eps": material("emittance_IR", const(EPS_COPPER), TLO, THI, "antenna conductor 0.14 = lowest registered metal emittance (H2-5 H25-27 lower end), used for a bare / plated copper antenna (verify)", ANALOG, "polished copper may be lower (verify)"),
    "OPT.collector.eps": material("emittance_IR", const(EPS_COLLECTOR), TLO, THI, "collector (INCONEL 600) 0.47 = anode midpoint (H2-5 H25-28); P3-R-04 collector emittance TBD", ANALOG, "0.14-0.8"),
}

# ------------------------------------------------------------------------------------------------ nodes
CC = ["PARAMETRIC"]


def node(id_, group, presence, represents, parts, biot, receives_note):
    return {"id": id_, "group": group, "presence": presence, "represents": represents, "parts": parts,
            "biot": biot, "note": receives_note}


def part(pid, cp, mass, mass_source):
    m = {"mass_kg": r9(mass)} if isinstance(mass, float) else mass
    return {"part_id": pid, "material_record_id": cp, **m, "mass_source": mass_source}


def biot(V, A, k):
    return {"volume_m3": r9(V), "conduction_area_m2": r9(A), "k_record_id": k}


NODES = [
    node("H1_ANODE", "HALL_BODY", "REQUIRED", "anode / gas distributor, INCONEL 600 (DBF1-MAT-01)",
         [part("P.anode", "MAT.in600.cp", m_an, "annulus r_in..r_out x 10 mm axial (assumed thickness) x 8470 kg/m^3 (P4 PR-011)")],
         biot(V_an, 2 * A_an + 2 * PI * (r_in + r_out) * V_an_t, "MAT.in600.k"), "anode material candidate CAND-02A"),
    node("H1_WALL_IN", "HALL_BODY", "REQUIRED", "inner channel wall, BN-SiO2 (DBF1-MAT-04)",
         [part("P.wall_in", "MAT.bns.cp", m_wi, "r_in - t_w .. r_in x L x 2000 kg/m^3 (assumed density, verify)")],
         biot(V_wi, A_wi_ch + A_wi_bk, "MAT.bns.k"), ""),
    node("H1_WALL_OUT", "HALL_BODY", "REQUIRED", "outer channel wall, BN-SiO2 (DBF1-MAT-04)",
         [part("P.wall_out", "MAT.bns.cp", m_wo, "r_out .. r_out + t_w x L x 2000 kg/m^3 (assumed density, verify)")],
         biot(V_wo, A_wo_ch + A_wo_bk, "MAT.bns.k"), ""),
    node("H1_POLE_IN", "HALL_BODY", "REQUIRED", "solid inner core + inner front pole, FeCo-2V (H1F-MA-01, H1F-MC-04)",
         [part("P.pole_in", "MAT.hiperco.cp", m_pi, "solid core pi r_core^2 L_core + pole disc pi (r_in - t_w)^2 x 5 mm, x 8110 kg/m^3 (H2-1 SRC-HIPERCO50)")],
         biot(V_pi, 2 * PI * r_core * L_core + 2 * A_pi_fr + A_pi_cav, "MAT.hiperco.k"), ""),
    node("H1_POLE_OUT", "HALL_BODY", "REQUIRED", "outer shell + outer front pole, pure iron (H1F-MA-02)",
         [part("P.pole_out", "MAT.armco.cp", m_po, "shell pi (r_body^2 - (r_body - 3 mm)^2) L_body + front annulus x 5 mm, x 7860 kg/m^3 (H2-1 SRC-ARMCO)")],
         biot(V_po, A_po_lat + A_c_co + 2 * A_po_fr, "MAT.armco.k"), ""),
    node("H1_BACKPLATE", "HALL_BODY", "REQUIRED", "back plate, pure iron; carries the isolated mount and the R_HALL heat-path doubler",
         [part("P.backplate", "MAT.armco.cp", m_bp, "disc pi r_body^2 x 5 mm x 7860 kg/m^3")],
         biot(V_bp, 2 * PI * r_body**2, "MAT.armco.k"), ""),
    node("H1_COIL_IN", "HALL_MAGNET", "REQUIRED", "inner winding (ceramic-insulated Ni-clad Cu, MCQ-EM-03)",
         [part("P.coil_in", "MAT.cu.cp", m_ci, "H2-1 RP-1 worst-case assumptions inner Cu mass 0.2765 kg")],
         biot(m_ci / RHO_CU, A_ci + A_c_ci, "MAT.cu.k"), ""),
    node("H1_COIL_OUT", "HALL_MAGNET", "REQUIRED", "outer winding (MCQ-EM-03)",
         [part("P.coil_out", "MAT.cu.cp", m_co, "H2-1 RP-1 worst-case assumptions outer Cu mass 1.243 kg")],
         biot(m_co / RHO_CU, A_co + A_c_co, "MAT.cu.k"), ""),
    node("H1_COIL_TRIM", "HALL_MAGNET", "CONDITIONAL", "trim winding provision (H1F-MC-02; present per DBF1-TH-01)",
         [part("P.coil_trim", "MAT.cu.cp", m_ct, "trim winding provision 0.05 kg (assumed)")],
         biot(m_ct / RHO_CU, 0.01, "MAT.cu.k"), "unpowered in every governing case (0 W explicit)"),
    node("N_VESSEL", "ICP_NEUTRALIZER", "REQUIRED", "dielectric tube, borosilicate (DBF1-ICP-07)",
         [part("P.vessel", "MAT.glass.cp", m_ve, "tube r_ap .. r_ap + 3 mm (assumed wall) x L_module x 2230 kg/m^3 (verify)")],
         biot(V_ve, A_ve_bore + A_col + A_ve_out, "MAT.glass.k"), ""),
    node("N_ANTENNA", "ICP_NEUTRALIZER", "REQUIRED", "13.56 MHz antenna, 3-turn 6 mm copper tube at r = 75 mm (assumed)",
         [part("P.antenna", "MAT.cu.cp", m_ant, "copper tube 6 x 1 mm, 3 turns at r 75 mm (assumed)")],
         biot(V_ant, A_ant, "MAT.cu.k"), ""),
    node("N_COLLECTOR", "ICP_NEUTRALIZER", "CONDITIONAL", "C-type ion collector on the bore, INCONEL 600, 0.10 m (DBF1-ICP-04, DBF1-MAT-03)",
         [part("P.collector", "MAT.in600.cp", m_col, "1 mm sheet, r 0.06 m, 0.10 m long (assumed thickness) x 8470 kg/m^3")],
         biot(V_col, 2 * A_col, "MAT.in600.k"), "collector material candidate CAND-02A"),
    node("N_HOUSING", "ICP_NEUTRALIZER", "CONDITIONAL", "module housing / RF shield, r_module 0.09 m (DBF1-ICP-02); aluminium alloy (assumed)",
         [part("P.housing", "MAT.al.cp", m_ho, "3 mm aluminium shell r_module x L_module + two 3 mm end flanges (assumed) x 2700 kg/m^3")],
         biot(V_ho, A_ho_out + A_ho_in + A_ho_dn + A_icp_up, "MAT.al.k"), ""),
    node("N_MATCH", "ICP_NEUTRALIZER", "CONDITIONAL", "co-located adjustable match (DBF1-RF-03)",
         [part("P.match", "MAT.box.cp", m_ma, "0.8 kg match box (assumed)")],
         biot(m_ma / RHO_AL, 0.06, "MAT.al.k"), ""),
    node("N_MOUNT", "ICP_NEUTRALIZER", "REQUIRED", "ICP mounting struts / bracket, titanium (assumed)",
         [part("P.mount", "MAT.ti.cp", m_mo, "0.3 kg titanium struts (assumed)")],
         biot(m_mo / RHO_TI, 0.03, "MAT.ti.k"), ""),
    node("R_HALL", "RADIATOR", "CONDITIONAL", "dedicated Hall radiator panel, zenith-facing, one side radiating (A9.12 OQ-A907-06)",
         [part("P.radiator", "MAT.al.cp", {"mass_kg_per_m2_of_A_RH": RH_AREAL}, "areal density 4.0 kg/m^2 (assumed, verify)")],
         {"volume_m3_per_m2_of_A_RH": r9(RH_AREAL / RHO_AL), "conduction_area_m2_per_m2_of_A_RH": 2.0, "k_record_id": "MAT.al.k"}, "area A_RH is the design lever"),
]

SURFACES = [
    # id, node, area, eps, alpha, enclosure, external, env_type
    ("S_AN", "H1_ANODE", A_an, "OPT.anode.eps", None, "E_EXT", True, None),
    ("S_WI_CH", "H1_WALL_IN", A_wi_ch, "OPT.bns.eps", None, "E_EXT", True, None),
    ("S_WO_CH", "H1_WALL_OUT", A_wo_ch, "OPT.bns.eps", None, "E_EXT", True, None),
    ("S_PI_FR", "H1_POLE_IN", A_pi_fr, "OPT.z93.eps", "OPT.z93.alpha", "E_EXT", True, "AFT_FACE"),
    ("S_PO_FR", "H1_POLE_OUT", A_po_fr, "OPT.z93.eps", "OPT.z93.alpha", "E_EXT", True, "AFT_FACE"),
    ("S_PO_LAT", "H1_POLE_OUT", A_po_lat, "OPT.z93.eps", "OPT.z93.alpha", "E_EXT", True, "LATERAL"),
    ("S_ICP_UP", "N_HOUSING", A_icp_up, "OPT.z93.eps", "OPT.z93.alpha", "E_EXT", True, None),
    ("S_WI_BK", "H1_WALL_IN", A_wi_bk, "OPT.bns.eps", None, "E_INNER", False, None),
    ("S_CI", "H1_COIL_IN", A_ci, "OPT.metal.eps", None, "E_INNER", False, None),
    ("S_PI_CAV", "H1_POLE_IN", A_pi_cav, "OPT.metal.eps", None, "E_INNER", False, None),
    ("S_WO_BK", "H1_WALL_OUT", A_wo_bk, "OPT.bns.eps", None, "E_OUTER", False, None),
    ("S_CO", "H1_COIL_OUT", A_co, "OPT.metal.eps", None, "E_OUTER", False, None),
    ("S_PO_CAV", "H1_POLE_OUT", A_po_cav, "OPT.metal.eps", None, "E_OUTER", False, None),
    ("S_VE_BORE", "N_VESSEL", A_ve_bore, "OPT.glass.eps", None, "E_BORE", True, None),
    ("S_COL", "N_COLLECTOR", A_col, "OPT.collector.eps", None, "E_BORE", True, None),
    ("S_VE_OUT", "N_VESSEL", A_ve_out, "OPT.glass.eps", None, "E_ANTGAP", False, None),
    ("S_ANT", "N_ANTENNA", A_ant, "OPT.copper.eps", None, "E_ANTGAP", False, None),
    ("S_HO_IN", "N_HOUSING", A_ho_in, "OPT.metal.eps", None, "E_ANTGAP", False, None),
    ("S_HO_OUT", "N_HOUSING", A_ho_out, "OPT.z93.eps", "OPT.z93.alpha", "E_ICPX", True, "LATERAL"),
    ("S_HO_DN", "N_HOUSING", A_ho_dn, "OPT.z93.eps", "OPT.z93.alpha", "E_ICPX", True, "AFT_FACE"),
    ("S_MO", "N_MOUNT", A_mo, "OPT.z93.eps", "OPT.z93.alpha", "E_ICPX", True, None),
    ("S_MA", "N_MATCH", A_ma, "OPT.z93.eps", "OPT.z93.alpha", "E_MATCH", True, "ZENITH"),
    ("S_RH", "R_HALL", None, "OPT.z93.eps", "OPT.z93.alpha", "E_RH", True, "ZENITH"),
]

area_of = {s[0]: s[2] for s in SURFACES}


def complete(rows, members):
    out = {}
    for k, row in rows.items():
        full = {m: r9(row.get(m, 0.0)) for m in members}
        out[k] = full
    return out


def encl(id_, rows, members, sinks, note):
    return {"id": id_, "members": members, "sinks": sinks, "view_factors": complete(rows, members), "note": note}


ext_members = ["S_AN", "S_WI_CH", "S_WO_CH", "S_PI_FR", "S_PO_FR", "S_PO_LAT", "S_ICP_UP", "SPACE_EXT"]
er = ext_rows()
for k in er:
    er[k]["SPACE_EXT"] = 1.0 - sum(v for kk, v in er[k].items())
bore_rows = {
    "S_VE_BORE": {"S_VE_BORE": F_cyl_cyl * A_ve_bore / A_bore_cyl, "S_COL": F_cyl_cyl * A_col / A_bore_cyl, "BORE_UP": F_cyl_end, "BORE_DN": F_cyl_end},
    "S_COL": {"S_VE_BORE": F_cyl_cyl * A_ve_bore / A_bore_cyl, "S_COL": F_cyl_cyl * A_col / A_bore_cyl, "BORE_UP": F_cyl_end, "BORE_DN": F_cyl_end},
}
F_ant_ve, F_ant_ho = 0.5, 0.5
F_ve_ant = A_ant * F_ant_ve / A_ve_out
F_ve_ho = 1 - F_ve_ant
F_ho_ve = A_ve_out * F_ve_ho / A_ho_in
F_ho_ant = A_ant * F_ant_ho / A_ho_in
F_ho_ho = 1 - F_ho_ve - F_ho_ant
ENCLOSURES = [
    encl("E_EXT", er, ext_members, [{"surface_id": "SPACE_EXT", "kind": "SPACE"}],
         "channel (anode, inner / outer wall faces: 2-D crossed strings on L = 103.2 mm, h = 12 mm with annular reciprocity), "
         "H-1 aft faces and lateral, ICP Hall-facing face; the channel exit and the aft faces view the ICP with the P3 "
         "parametric-study F of the nearest registered grid row (" + S_P3 + " /radiative_view_parametric_study, row L/Ro 1.0, "
         "rap/Ro 1.5, wall/Ro 0.6, H/Ro 3.0, tau 0) and SPACE otherwise; radiation leaving the channel through the exit is "
         "split like the exit aperture (diffuse-aperture approximation); the ICP Hall-facing receiver lumps the upstream face "
         "and the bore entrance on N_HOUSING; the rest of its view is SPACE (spacecraft-body view not modelled)"),
    encl("E_INNER", {"S_WI_BK": {"S_CI": A_ci / A_wi_bk, "S_PI_CAV": A_pi_cav / A_wi_bk},
                     "S_CI": {"S_WI_BK": 1.0}, "S_PI_CAV": {"S_WI_BK": 1.0}},
         ["S_WI_BK", "S_CI", "S_PI_CAV"], [],
         "inner wall back face around the inner coil (concentric, F coil->wall = 1) and the exposed inner core / pole underside"),
    encl("E_OUTER", {"S_WO_BK": {"S_CO": A_co / A_wo_bk, "S_PO_CAV": A_po_cav / A_wo_bk},
                     "S_CO": {"S_WO_BK": 1.0}, "S_PO_CAV": {"S_WO_BK": 1.0}},
         ["S_WO_BK", "S_CO", "S_PO_CAV"], [], "outer wall back face inside the outer coil (concentric, F coil->wall = 1); closed body (no open-body lever)"),
    encl("E_BORE", bore_rows, ["S_VE_BORE", "S_COL", "BORE_UP", "BORE_DN"],
         [{"surface_id": "BORE_UP", "kind": "SPACE"}, {"surface_id": "BORE_DN", "kind": "SPACE"}],
         "ICP bore r_ap 0.06 m x L_module 0.15 m: Howell C-40 disc-to-disc F = %.6f, cylinder-to-each-end F = %.6f; vessel and collector share the cylinder in proportion to area; both ends open (the upstream end views the H-1 exit, modelled as SPACE)" % (F_dd, F_cyl_end)),
    encl("E_ANTGAP", {"S_ANT": {"S_VE_OUT": F_ant_ve, "S_HO_IN": F_ant_ho},
                      "S_VE_OUT": {"S_ANT": F_ve_ant, "S_HO_IN": F_ve_ho},
                      "S_HO_IN": {"S_VE_OUT": F_ho_ve, "S_ANT": F_ho_ant, "S_HO_IN": F_ho_ho}},
         ["S_VE_OUT", "S_ANT", "S_HO_IN"], [], "annular gap tube / antenna / housing, closed by the housing end flanges; antenna views tube and housing half each (assumed); other rows by reciprocity and summation"),
    encl("E_ICPX", {"S_HO_OUT": {"SPACE_ICP": 1.0}, "S_HO_DN": {"SPACE_ICP": 1.0}, "S_MO": {"SPACE_ICP": 1.0}},
         ["S_HO_OUT", "S_HO_DN", "S_MO", "SPACE_ICP"], [{"surface_id": "SPACE_ICP", "kind": "SPACE"}], "ICP outward surfaces view SPACE (convex; spacecraft view not modelled)"),
    encl("E_MATCH", {"S_MA": {"SPACE_MA": 1.0}}, ["S_MA", "SPACE_MA"], [{"surface_id": "SPACE_MA", "kind": "SPACE"}], "match-box radiating face, zenith"),
    encl("E_RH", {"S_RH": {"SPACE_RH": 1.0}}, ["S_RH", "SPACE_RH"], [{"surface_id": "SPACE_RH", "kind": "SPACE"}], "R_HALL radiating face, zenith; back face insulated"),
]


def link_g(id_, a, b, g, derivation, ec=ASSUMED, unc="design value", boundary_temp=None):
    d = {"id": id_, "type": "LUMPED_G", "a": a, "b": b, "G_W_K": r9(g) if isinstance(g, float) else g,
         "derivation": derivation, "evidence_class": ec, "uncertainty": unc}
    if boundary_temp:
        d["boundary_temperature"] = boundary_temp
    return d


LINKS = [
    link_g("L_AN_BP", "H1_ANODE", "H1_BACKPLATE", 1.0,
           "anode-to-back-plate conductance (isolators + feed tube) = 1.0 W/K, the upper end of H2-5 H25-31 [0.1, 1] W/K: a design REQUIREMENT on the anode isolator / feed path (A9.2 anode thermal-design-first), reported as such"),
    link_g("L_WI_BP", "H1_WALL_IN", "H1_BACKPLATE", G_wi,
           "series: BN axial conduction k_BN 29 x 0.75 (H25-24 note / H25-45) over 0.75 L (H25-44) through 2 pi r_m t_w, and support-ring contact h_c 1627.5 W/(m^2 K) (H25-30 midpoint) x 2 pi r_m x 3.5 mm (H25-21 midpoint)",
           INFERRED, "H2-5 ranges H25-21/24/30/44/45"),
    link_g("L_WO_BP", "H1_WALL_OUT", "H1_BACKPLATE", G_wo, "as L_WI_BP for the outer wall", INFERRED, "H2-5 ranges"),
    {"id": "L_CI_PI", "type": "CONTACT", "a": "H1_COIL_IN", "b": "H1_POLE_IN", "h_c_W_m2K": r9(H_C_COIL), "A_c_m2": r9(A_c_ci),
     "derivation": "coil bore on the solid core: h_c x 2 pi r_core L_coil (H2-5 coil link form); h_c = 155 W/(m^2 K), the H25-30 lower end, for an unpotted porous ceramic-insulated winding (MCQ-EM-03) on iron in vacuum (no potting / bonding registered): conservative for the coil node; it also keeps the lumped H1_POLE_IN node inside D-02 (at the midpoint 1627.5 the node Biot estimate is ~0.14)", "evidence_class": INFERRED, "uncertainty": "h_c 155-3100 W/(m^2 K) (SENS-HC-HI)"},
    {"id": "L_CO_PO", "type": "CONTACT", "a": "H1_COIL_OUT", "b": "H1_POLE_OUT", "h_c_W_m2K": r9(H_C_COIL), "A_c_m2": r9(A_c_co),
     "derivation": "outer winding on the shell bore: h_c x 2 pi (r_body - 3 mm) L_coil; h_c 155 as L_CI_PI", "evidence_class": INFERRED, "uncertainty": "h_c 155-3100"},
    {"id": "L_CT_BP", "type": "CONTACT", "a": "H1_COIL_TRIM", "b": "H1_BACKPLATE", "h_c_W_m2K": r9(H_C_COIL), "A_c_m2": A_c_ct,
     "derivation": "trim winding pad 0.002 m^2 on the back plate (assumed)", "evidence_class": ASSUMED, "uncertainty": "provision"},
    {"id": "L_PI_BP", "type": "CONDUCTION", "a": "H1_POLE_IN", "b": "H1_BACKPLATE", "k_record_id": "MAT.hiperco.k",
     "shape": {"kind": "SLAB", "area_m2": r9(A_core), "length_m": r9(L_core_eff)},
     "derivation": "solid FeCo-2V core pi r_core^2 (r_core = r_in - t_w - 0.5 mm - inner coil build 6.826 mm = %.6f m) over L_core 0.11 m (H25-17 midpoint) plus the core-to-back-plate joint folded in as k/h_c = %.6f m (series slab form, exact for constant k)" % (r_core, K_HIPERCO / H_C),
     "evidence_class": INFERRED, "uncertainty": "k assumed (verify); joint h_c 155-3100"},
    {"id": "L_PO_BP", "type": "CONDUCTION", "a": "H1_POLE_OUT", "b": "H1_BACKPLATE", "k_record_id": "MAT.armco.k",
     "shape": {"kind": "SLAB", "area_m2": r9(A_shell), "length_m": r9(L_shell_eff)},
     "derivation": "outer shell annulus 3 mm (H2-1 outer_core_t_mm) over L_body 108.2 mm (H1F-MC-06) plus the shell-to-back-plate joint folded in as k(673 K)/h_c (approximation for the joint term)",
     "evidence_class": INFERRED, "uncertainty": "grade multiplier 0.8-1.02; joint h_c 155-3100"},
    link_g("L_BP_RH", "H1_BACKPLATE", "R_HALL", "G_RH (design lever)", "heat-path doubler back plate -> R_HALL: design lever G_RH (grid)"),
    link_g("L_BP_SC", "H1_BACKPLATE", "B_SC", 0.2, "SCI-A isolated H-1 mount: 0.2 W/K, lower end of H25-33 (A9.12 OQ-A907-06 isolated mount; REFERENCE_PENDING_ICD, DBF1-TH-02)", ASSUMED, "REFERENCE_PENDING_ICD", "T_SC"),
    link_g("L_RH_SC", "R_HALL", "B_SC", 0.1, "SCI-A radiator standoffs to the spacecraft: 0.1 W/K (assumed; REFERENCE_PENDING_ICD)", ASSUMED, "REFERENCE_PENDING_ICD", "T_SC"),
    link_g("L_MO_BP", "N_MOUNT", "H1_BACKPLATE", 0.2, "ICP struts to the H-1 back plate: 0.2 W/K (assumed; P3-K-02 TBD)"),
    link_g("L_MO_SC", "N_MOUNT", "B_SC", 0.1, "SCI-A ICP bracket to the spacecraft: 0.1 W/K (assumed; P3-K-03 TBD; REFERENCE_PENDING_ICD)", ASSUMED, "REFERENCE_PENDING_ICD", "T_SC"),
    link_g("L_HO_MO", "N_HOUSING", "N_MOUNT", 1.0, "housing to bracket (bolted): 1.0 W/K (assumed; P3-K-01 TBD)"),
    link_g("L_VE_HO", "N_VESSEL", "N_HOUSING", 0.5, "tube end seats in the housing flanges: 0.5 W/K (assumed)"),
    link_g("L_ANT_HO", "N_ANTENNA", "N_HOUSING", 0.3, "antenna standoffs / feedthrough: 0.3 W/K (assumed; P3-K-04 TBD)"),
    link_g("L_COL_HO", "N_COLLECTOR", "N_HOUSING", 0.2, "collector through its 350 V-class insulator: 0.2 W/K (assumed; P3-K-05 TBD)"),
    link_g("L_COL_VE", "N_COLLECTOR", "N_VESSEL", 0.5, "collector seated on the tube bore (unbonded contact): 0.5 W/K (assumed)"),
    link_g("L_MA_MO", "N_MATCH", "N_MOUNT", 0.5, "match box on the ICP bracket: 0.5 W/K (assumed; P3-K-06 TBD)"),
    link_g("L_MA_PPU", "N_MATCH", "B_PPU_RF", 0.05, "RF feed line / harness conduction to the RF generator: 0.05 W/K (assumed)", ASSUMED, "assumed", "T_PPU"),
]

# ------------------------------------------------------------------------------------------------ limits
LIMITS = [
    {"node": "H1_WALL_IN", "upper_C": 900.0, "class": "SOURCED_GUIDE", "source": src(S_MATG, "/analyses/5/rows/2"),
     "basis": "BN-SiO2 (HeBoSint CL-S 200, hBN + SiO2) oxidizing use temperature ~900 degC (P8 DA-06 row; supplier guide, NOT_VALIDATED); 900 - 50 = 850 degC with 1.2 x loads, as A9-07 REV-45 and the P8 screening ceiling; the M26 distributor value (950 degC ceiling) and the BN backups are reported beside it (materials_screening)"},
    {"node": "H1_WALL_OUT", "upper_C": 900.0, "class": "SOURCED_GUIDE", "source": src(S_MATG, "/analyses/5/rows/2"), "basis": "as H1_WALL_IN"},
    {"node": "H1_POLE_IN", "upper_C": 938.0, "class": "NECESSARY_CEILING", "source": src(S_H1F, "/parameters/56"),
     "basis": "FeCo-2V Curie 938 degC (SRC-HIPERCO50 p. 2): a necessary ceiling only (H1F-MA-03), the usable limit is B_sat(T) of the grade (HW-MC-13)"},
    {"node": "H1_POLE_OUT", "upper_C": 754.0, "class": "NECESSARY_CEILING", "source": src(S_A914, "/decisions/F5-OQ-03"),
     "basis": "A9.14 F5-OQ-03 USE_754C_NECESSARY_CEILING_PENDING_GRADE_DATA (H1F-MA-04); not a usable limit"},
    {"node": "H1_BACKPLATE", "upper_C": 754.0, "class": "NECESSARY_CEILING", "source": src(S_A914, "/decisions/F5-OQ-03"), "basis": "as H1_POLE_OUT"},
    {"node": "H1_COIL_IN", "upper_C": 537.778, "class": "SOURCED_GUIDE", "source": src(S_H1F, "/parameters", "H1F-CO-11"),
     "basis": "MCQ-EM-03 Ceramawire HT (Kulgrid) 1000 F continuous (supplier, not validated; " + S_MCQ + "); H1F-CO-11 design ceiling 487.778 degC"},
    {"node": "H1_COIL_OUT", "upper_C": 537.778, "class": "SOURCED_GUIDE", "source": src(S_H1F, "/parameters", "H1F-CO-11"), "basis": "as H1_COIL_IN"},
    {"node": "H1_COIL_TRIM", "upper_C": 537.778, "class": "SOURCED_GUIDE", "source": src(S_H1F, "/parameters", "H1F-CO-11"), "basis": "as H1_COIL_IN (same wire family assumed)"},
    {"node": "H1_ANODE", "upper_C": None, "class": "REQUIREMENT_ONLY", "source": src(S_P4, "/criteria/0"),
     "basis": "P4 CR-01: T_validated,continuous only from stage-2 evidence; melting range and supplier ratings are not a limit; no new arbitrary limit. Output: required T_validated >= T_max + 50 K; FAIL if that exceeds the INCONEL 600 solidus 1354 degC (P4 PR-018)",
     "absolute_ceiling_C": 1354.0, "absolute_ceiling_source": src(S_P4, "/property_records", "PR-018 melting range 1354-1413 degC")},
    {"node": "N_COLLECTOR", "upper_C": None, "class": "REQUIREMENT_ONLY", "source": src(S_P4, "/criteria/0"), "basis": "as H1_ANODE (APP-COLLECTOR)",
     "absolute_ceiling_C": 1354.0, "absolute_ceiling_source": src(S_P4, "/property_records", "PR-018")},
    {"node": "N_VESSEL", "upper_C": 490.0, "class": "ASSUMED_FROM_MEMORY", "source": None,
     "basis": "borosilicate (pyrex-class) annealed extreme-service temperature 490 degC from memory (verify); strain point ~510 degC (verify); P3-R-03 dielectric not selected"},
    {"node": "N_ANTENNA", "upper_C": None, "class": "REQUIREMENT_ONLY", "source": None, "basis": "antenna conductor / plating / standoff limit not registered (P2 TBD): output required capability T_max + 50 K"},
    {"node": "N_HOUSING", "upper_C": None, "class": "REQUIREMENT_ONLY", "source": None, "basis": "housing material and exterior coating not selected: output required capability T_max + 50 K"},
    {"node": "N_MOUNT", "upper_C": None, "class": "REQUIREMENT_ONLY", "source": None, "basis": "bracket material / coating not selected: output required capability"},
    {"node": "N_MATCH", "upper_C": 110.0, "lower_operating_C": -20.0, "lower_nonoperating_C": -40.0, "class": "DERATED_ELECTRONICS",
     "source": src(S_LIM, "/records/eee_inst_002_magnetics/values/table4_rows"),
     "basis": "EEE-INST-002 M1 Table 4 MIL-PRF-27 class S inductive device 130 degC max operating, derated 110 degC (the 50,000 h life basis covers the 15,000 h firing basis); lower limits -20 / -40 degC operating / non-operating are selected unit qualification values from memory (verify)"},
    {"node": "R_HALL", "upper_C": None, "class": "REQUIREMENT_ONLY", "source": src(S_H1F, "/parameters/59"),
     "basis": "exterior coating limit TBD (H1F-MA-06: no closure relying on the coating before its limit is sourced): output required coating capability"},
]
COATED_NODES = ["H1_POLE_IN", "H1_POLE_OUT", "N_HOUSING", "N_MOUNT", "N_MATCH", "R_HALL"]

# ------------------------------------------------------------------------------------------------ prereg
prereg = {
    "schema": "abep_closure_thermal_cases_prereg_v1",
    "id": "P7-THERMAL-CASES-PREREG-v1",
    "item": "P7 thermal closure (A9.38 priority 7)",
    "lane": "L-THERMAL",
    "date": "2026-10-08",
    "status": "PREREGISTERED_BEFORE_PRODUCTION_CASES",
    "base_commit": "42bb83a",
    "authority": [src(S_A938), src(S_A937), src(S_DBF1), src(S_DBF1_LOCK), src(S_BOARD)],
    "dbf1_items_used": ["DBF1-TH-01", "DBF1-TH-02", "DBF1-TH-03", "DBF1-H1-01", "DBF1-H1-02", "DBF1-H1-03", "DBF1-H1-04",
                        "DBF1-H1-05", "DBF1-H1-06", "DBF1-BZ-02", "DBF1-BZ-05", "DBF1-RF-01", "DBF1-RF-02", "DBF1-RF-03",
                        "DBF1-ICP-02", "DBF1-ICP-04", "DBF1-ICP-07", "DBF1-PWR-01", "DBF1-PWR-03", "DBF1-PWR-04",
                        "DBF1-IN-08", "DBF1-MAT-01", "DBF1-MAT-03", "DBF1-MAT-04"],
    "what_this_is_not": [
        "not a flight-conditional thermal prediction: FLIGHT_CONDITIONAL is NOT_EVALUATED by NP-THERMAL governance (no host thermal ICD, credible Hall set EMPTY, NP-ICP not admitted); every case is PARAMETRIC (label PARAMETRIC_NOT_A_PREDICTION)",
        "not a validation: the model is VERIFIED, NOT_VALIDATED (" + S_NPT_VER + ")",
        "not a topology change: the DBF1-TH-01 node set is used exactly (R_ICP absent; no subdivision, junction or extra node)",
        "not a change to any DBF-1 value, owner decision, admitted or scored record",
    ],
    "model": {
        "id": "NP-THERMAL-CATHODELESS", "version": "2.0.0", "entry": "abep_subsystems::thermal::run_case_v2",
        "prereg": src(S_NPT2), "prereg_lock": src(S_NPT2_LOCK), "verification": src(S_NPT_VER),
        "case_class": "PARAMETRIC", "topology_scope": "NP_THERMAL_NETWORK", "configuration": "hall_icp_neutralizer",
        "match_colocated": True, "magnet_load_mode": "FIXED_POWER",
        "anode_material_candidate_id": "CAND-02A", "collector_material_candidate_id": "CAND-02A",
        "why_parametric": "run_case_v2 returns NOT_EVALUATED for FLIGHT_CONDITIONAL here (SPACECRAFT_THERMAL_ICD_ABSENT, CREDIBLE_HALL_TRANSPORT_SET_EMPTY, NP_ICP_NEUTRALIZER_NOT_ADMITTED); PARAMETRIC accepts registered engineering loads labelled as such",
        "record_evidence_rule": "owner-allocation values are refused as model inputs by NP-THERMAL; loads derived from owner allocations enter as 'assumed' records whose source names the allocation",
    },
    "topology": {
        "solved_nodes": [n["id"] for n in NODES],
        "absent": ["R_ICP"],
        "boundaries_used": ["B_SC (SCI-A at H1_BACKPLATE, N_MOUNT, R_HALL)", "B_PPU_RF (N_MATCH harness link)", "SPACE", "ENV"],
        "boundaries_unused": {"B_FEED": "the anode feed-tube conduction is inside L_AN_BP (H25-31 'isolators + gas feed')", "B_FACILITY": "flight cases only"},
        "rule": "exactly the DBF1-TH-01 node set; no SUBDIVISION, MASSLESS_SERIES_JUNCTION or other node; a D-02 (Biot) refusal is reported as OUT_OF_DOMAIN and is never suppressed (its remedy, a registered subdivision, needs an addendum before a rerun)",
    },
    "geometry_primitives": {
        "r_in_m": num(r_in, "m", src(S_DBF1, "/items", "DBF1-H1-04"), "owner-allocation", "design value"),
        "r_out_m": num(r_out, "m", src(S_DBF1, "/items", "DBF1-H1-04"), "owner-allocation", "design value"),
        "L_channel_m": num(L_ch, "m", src(S_DBF1, "/items", "DBF1-H1-03"), "owner-allocation", "design value"),
        "t_wall_m": num(t_w, "m", src(S_H21, "/coil_design/cases/2/t_wall_mm"), MODEL, "H25-15 range 3-6 mm"),
        "inner_coil_build_m": num(build_ci, "m", src(S_H21, "/coil_design/cases/2/inner_coil_build_mm"), MODEL, "lumped sizing"),
        "coil_axial_length_m": num(L_coil, "m", src(S_H21, "/coil_design/cases/2/coils/inner/window_axial_mm"), MODEL, "lumped sizing"),
        "coil_clearance_m": num(clear, "m", "assumed", ASSUMED, "0.5 mm (assumed)"),
        "r_core_solid_m": num(r_core, "m", "derived: r_in - t_wall - clearance - inner coil build (solid core, H1F-MC-04 " + S_H1F + " /parameters/27)", MODEL, "follows the inputs"),
        "L_core_m": num(L_core, "m", src(S_H25, "/design_parameters", "H25-17 midpoint of [0.10, 0.12] m"), ASSUMED, "0.10-0.12 m"),
        "r_body_m": num(r_body, "m", src(S_H21, "/coil_design/cases/2/body_OD_mm"), MODEL, "lumped sizing"),
        "t_shell_m": num(t_shell, "m", src(S_H21, "/coil_design/cases/2/outer_core_t_mm"), MODEL, "lumped sizing"),
        "t_backplate_m": num(t_bp, "m", src(S_H21, "/coil_design/cases/2/back_plate_t_mm"), MODEL, "lumped sizing"),
        "L_body_m": num(L_body, "m", src(S_H1F, "/parameters/29"), MODEL, "RP-1 anchor"),
        "icp_L_standoff_m": num(L_so, "m", src(S_DBF1, "/items", "DBF1-ICP-02"), ASSUMED, "F6 state probe"),
        "icp_r_aperture_m": num(r_ap, "m", src(S_DBF1, "/items", "DBF1-ICP-02"), ASSUMED, "F6 state probe"),
        "icp_r_module_m": num(r_mod, "m", src(S_DBF1, "/items", "DBF1-ICP-02"), ASSUMED, "F6 state probe"),
        "icp_L_module_m": num(L_mod, "m", src(S_DBF1, "/items", "DBF1-ICP-02"), ASSUMED, "F6 state probe"),
        "icp_collector_length_m": num(L_col, "m", src(S_DBF1, "/items", "DBF1-ICP-04"), "as-reported", "Takahashi anchor"),
        "icp_tube_wall_m": num(t_tube, "m", "assumed", ASSUMED, "verify at ICD ICP-07"),
        "icp_housing_wall_m": num(t_hous, "m", "assumed", ASSUMED, "verify"),
        "icp_antenna": {"turns": ant_turns, "tube_od_m": ant_d, "tube_wall_m": ant_wall, "radius_m": r_ant, "source": "assumed (P2 antenna design TBD)", "evidence_class": ASSUMED},
        "anode_axial_thickness_m": num(V_an_t, "m", "assumed", ASSUMED, "H1F-AN-03 TBD"),
        "densities_kg_m3": {"INCONEL600": RHO_IN600, "Hiperco50": RHO_HIPERCO, "iron": RHO_IRON, "BN-SiO2": RHO_BNS, "copper": RHO_CU, "borosilicate": RHO_GLASS, "aluminium": RHO_AL, "titanium": RHO_TI,
                            "sources": "IN600 P4 PR-011; Hiperco 50 / iron H2-1 materials (SRC-HIPERCO50 p. 2, SRC-ARMCO p. 5); BN-SiO2, copper, glass, aluminium, titanium from memory (verify)"},
    },
    "materials": MATERIALS,
    "optics": OPTICS,
    "nodes": NODES,
    "surfaces": [{"id": s[0], "node": s[1], "area_m2": r9(s[2]) if s[2] is not None else "A_RH (design lever)", "eps_record_id": s[3],
                  "alpha_record_id": s[4], "enclosure": s[5], "external": s[6], "env_type": s[7]} for s in SURFACES],
    "enclosures": ENCLOSURES,
    "links": LINKS,
    "boundary_temperatures": {
        "T_SC_K": {"hot": 333.15, "cold": 293.15, "icd_sensitivity": [293.15, 313.15, 333.15],
                   "source": src(S_H1F, "/parameters/63", "H1F-TH-02 owner row 85: 20 / 40 / 60 degC interface cases carried"), "status": "REFERENCE_PENDING_ICD"},
        "T_PPU_K": {"value": 303.15, "basis": "the electronics design allowable of the PPU / RF-generator baseplate (boundary_units rule below)"},
    },
    "environment": {
        "attitude": "flow-aligned (DBF1-DRAG-02): body x along the velocity, z nadir, y orbit normal; the H-1 axis along x with the exhaust aft (-x); H-1 and ICP lateral surfaces are cylinders about x; exit / pole / ICP downstream faces have normal -x (AFT_FACE); R_HALL and the match-box radiating face are zenith-facing panels (ZENITH); no surface faces the ram (aerodynamic heating A_ram = 0 on every registered surface: the propulsion assembly sits in the wake of the intake / spacecraft)",
        "orbit_set": "180-230 km circular (governed design-state set " + S_DS2 + " altitude band); inclination / LTAN TBD (broad envelope), so every beta angle is admitted",
        "earth_and_orbit": "R_EARTH, MU_EARTH from " + S_CONST + " (abep_types::constants); eclipse fraction from the admitted kernel abep_mission::propagation::eclipse_fraction (" + S_PROP + ", PARITY-C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION-V1); the harness's shadow-entry angles must reproduce that fraction to 1e-9",
        "beta_cases": {
            "BSTAR": "the smallest beta with zero eclipse at the case altitude (full-sun orbit; eclipse_fraction(h, beta*) = 0): the continuous-sun hot case",
            "B0": "beta = 0 (maximum eclipse, subsolar albedo at orbit noon)",
        },
        "fluxes": {
            "hot": {"S_W_m2": 1414.0, "albedo": 0.26, "OLR_W_m2": 275.0, "source": src(S_H25, "/design_parameters", "H25-37 / H25-38 (EXT-NASA-TM2001 hot cases, max albedo and max OLR combined)")},
            "cold": {"S_W_m2": 1322.0, "albedo": 0.0, "OLR_W_m2": 218.0, "source": src(S_H25, "/design_parameters", "H25-37 / H25-39; cold albedo set to 0 (conservative bound for the cold case)")},
        },
        "view_factor_method": {
            "plate_to_earth": "F(theta) = (1/pi) * integral over the Earth cap (half-angle rho, sin rho = R/(R+h)) of max(0, n.d) dOmega, n at angle theta from nadir; midpoint quadrature 720 (polar) x 1440 (azimuth); verified against sin^2(rho) cos(theta) for theta <= pi/2 - rho to 1e-5",
            "LATERAL": "F_earth = azimuthal mean of F(theta) for the normal swept around the x axis (180 normal directions, plate quadrature 180 x 360 each); F_sun = sin(psi)/pi with cos(psi) = s.x (projected / total lateral area); F_alb = F_earth * max(0, s.zenith)",
            "AFT_FACE": "normal -x: F_earth = F(pi/2); F_sun = max(0, -s.x); F_alb = F_earth * max(0, s.zenith)",
            "ZENITH": "normal -z (zenith): F_earth = 0, F_alb = 0, F_sun = max(0, s.zenith)",
            "sun_vector": "orbit angle u from the orbit-noon point: s.zenith = cos(beta) cos(u), s.x = -cos(beta) sin(u), s.y = sin(beta); in shadow when s.zenith < 0 and sqrt(1 - s.zenith^2) < R/(R+h) (cylindrical shadow, the admitted kernel's model)",
            "albedo_factor": "albedo flux on a surface = a S F_alb with F_alb = F_earth x cosine of the subsatellite solar zenith angle (standard approximation, Gilmore, verify)",
        },
        "steady_hot_rule": "BSTAR cases are STEADY: each surface carries its own orbit-maximum absorbed flux (sun, albedo, OLR evaluated at the u that maximises alpha S F_sun + alpha a S F_alb + eps OLR F_earth for that surface; 1440 u steps); maxima of different surfaces occur at different u, so the set is conservative",
        "periodic_rule": "B0 cases are ORBIT_TRANSIENT_PERIODIC over one orbit period P = 2 pi sqrt((R+h)^3 / mu) with ZOH series of F_sun, illumination and F_alb on 72 equal u intervals plus the exact shadow entry / exit breakpoints, step dt = P / 144, T_init from an ORBIT_AVERAGE_STEADY solve of the same case; reported per node: the max (hot) or min (cold) over the converged orbit",
        "aero": "rho = max design-state density at the case altitude (" + S_DS2 + "), V = circular orbital speed; A_ram = 0 for every surface, so Q_aero = 0 (recorded)",
        "not_modelled": ["ICP shading of the H-1 aft faces (conservative for hot)", "spacecraft-body views (SPACE assumed)", "sunlight through the channel exit (<= alpha S A_exit F_sun ~ 1 W)", "aperture back-radiation from the plume", "albedo / IR anisotropy beyond the cosine approximation"],
    },
    "loads": {
        "input_file": "docs/closure/thermal/thermal_load_inputs_v1.json (versioned: a later version from the L-POWER-ICD ledger / DCR-001 compressor reruns this identical method)",
        "hall_interface": {
            "record": "IF-HALL-THERMAL-v1, producer P7-PARAMETRIC-HALL-LOADS, case_class PARAMETRIC, every value evidence class 'assumed' (source names the allocation / analog), validation NOT_VALIDATED",
            "P_hall_discharge_W": "P_d",
            "P_hall_jet_W": "0 (the trivial lower bound of the exported directed power; no admitted Hall map)",
            "Q_hall_anode_W": "f_anode x P_d",
            "Q_hall_wall_inner_W": "f_walls x P_d x share_inner",
            "Q_hall_wall_outer_W": "f_walls x P_d x (1 - share_inner)",
            "Q_hall_pole_W": "f_pole x P_d, partition H1_POLE_IN 1.0 (inner front pole; EXT-MYERS2016 Table 3)",
            "Q_hall_plasma_radiation_W": "0 (contained in the calorimetric analog fractions), partition EXPORT 1.0",
            "Q_hall_return_to_icp_W": "I_d x E_return, I_d = P_d / V_d (Hall discharge current closing through the ICP collector, HK-08; N_COLLECTOR)",
            "Q_hall_plume_to_icp_W": "0 in governing cases; its allowable is derived (allowables AL-PLUME); partition from the input file",
            "Q_hall_coil_*_W": "FIXED_POWER per coil from the input file",
            "heat_load_factor": "every key (including the P_d reference) x 1.2 in hot cases, x 1/1.2 in cold operating cases (DBF1-TH-03), 0 in NON_FIRING",
        },
        "icp_interface": {
            "record": "IF-ICP-THERMAL-v2, configuration PARAMETRIC, scenario member 'P7-PARAMETRIC/<case>', every value evidence 'assumed'; producer fields are the locked v2 anchor (format only: the values are registered engineering assumptions, not an NP-ICP output)",
            "identities": "P_icp_rf_source_DC = P_fwd / eta_RF; conversion loss = P_rf_source_DC - P_fwd; P_fwd = P_refl + Q_line + Q_match + Q_coil + P_abs; Q_match = f_match P_fwd; P_abs = eta_p (P_fwd - P_refl - Q_line - Q_match); Q_coil = (1 - eta_p)(...); P_abs split into plasma wall / radiation / extraction / upstream / downstream by the input fractions; P_collector_bias = 0 and TK-12 = TK-13 = 0 (the collector heat is booked once, through HK-08); slot sum = rf_source_DC + matching_DC + collector_bias; TK-14 / TK-15 NOT_INSTALLED = 0",
            "partitions": "TK-06 split, TK-07 node shares, f_rad and f_up from the input file (registered RI-PART records)",
            "heat_load_factor": "every key x the case factor (the identities stay exact)",
        },
        "sources_of_values": "see the input file: every value carries its source, evidence class and uncertainty",
    },
    "cases": [
        {"id": "TC1-HOT-H-BSTAR", "governing": True, "alt_km": 180.0, "beta": "BSTAR", "solver": "STEADY", "flux": "hot", "load_set": "HOT_H", "factor": 1.2, "T_SC": "hot", "supply_mode": "AIR_PRIMARY"},
        {"id": "TC2-HOT-H-B0", "governing": True, "alt_km": 180.0, "beta": "B0", "solver": "ORBIT_TRANSIENT_PERIODIC", "flux": "hot", "load_set": "HOT_H", "factor": 1.2, "T_SC": "hot", "supply_mode": "AIR_PRIMARY"},
        {"id": "TC3-HOT-I-BSTAR", "governing": True, "alt_km": 180.0, "beta": "BSTAR", "solver": "STEADY", "flux": "hot", "load_set": "HOT_I", "factor": 1.2, "T_SC": "hot", "supply_mode": "AIR_PRIMARY"},
        {"id": "TC4-HOT-I-B0", "governing": True, "alt_km": 180.0, "beta": "B0", "solver": "ORBIT_TRANSIENT_PERIODIC", "flux": "hot", "load_set": "HOT_I", "factor": 1.2, "T_SC": "hot", "supply_mode": "AIR_PRIMARY"},
        {"id": "TC5-COLD-OP-B0", "governing": True, "alt_km": 230.0, "beta": "B0", "solver": "ORBIT_TRANSIENT_PERIODIC", "flux": "cold", "load_set": "COLD_OP", "factor": 1.0 / 1.2, "T_SC": "cold", "supply_mode": "AIR_PRIMARY"},
        {"id": "TC6-COLD-NONOP-B0", "governing": True, "alt_km": 230.0, "beta": "B0", "solver": "ORBIT_TRANSIENT_PERIODIC", "flux": "cold", "load_set": "NON_FIRING", "factor": 0.0, "T_SC": "cold", "supply_mode": "NON_FIRING"},
        {"id": "TC7-HOT-H-BSTAR-XE", "governing": False, "alt_km": 180.0, "beta": "BSTAR", "solver": "STEADY", "flux": "hot", "load_set": "HOT_H", "factor": 1.2, "T_SC": "hot", "supply_mode": "XE_CONTINGENCY",
         "purpose": "XE_CONTINGENCY carries the identical registered load set (the analog fractions are xenon values): identity check against TC1"},
        {"id": "S1-BAND-1350-BSTAR", "governing": False, "alt_km": 180.0, "beta": "BSTAR", "solver": "STEADY", "flux": "hot", "load_set": "BAND_MAX", "factor": 1.2, "T_SC": "hot", "supply_mode": "AIR_PRIMARY",
         "purpose": "P_d at the DBF1-H1-06 band upper end 1350 W (outside the 1350 W bus allocation once the ICP and common loads are counted): reported, not governing"},
    ],
    "solver_initial": {
        "STEADY": "T_init equal for every node, tried in the order 500, 350, 800, 1100 K; the first CONVERGED solve is taken (numerical start only; the steady solution of this network is unique); none converged -> the case is reported with its status",
        "ORBIT_AVERAGE_STEADY": "pre-solve of each periodic case with the same start list",
        "ORBIT_TRANSIENT_PERIODIC": "T_init = the ORBIT_AVERAGE_STEADY solution of the same case",
        "heater_sizing": "TC5 / TC6: if N_MATCH falls below its operating / non-operating lower limit, bisection (40 iterations or 0.05 W) on a Q_thermal_control_W heater on N_MATCH in [0, 200] W to the limit",
    },
    "load_sets": {
        "HOT_H": "Hall at the allocation bound P_d,hot (input file) at V_d,min with the upper analog fractions, coils hot, ICP at P_fwd,anchor",
        "HOT_I": "Hall at P_d,band,min at V_d,min with the upper analog fractions, coils hot, ICP at P_fwd,max (DBF1-RF-02 envelope end)",
        "COLD_OP": "Hall at P_d,band,min at V_d,max with the lower analog fractions, coils cold, ICP at P_fwd,anchor, E_return,cold",
        "NON_FIRING": "every interface key exactly 0 (AS-03)",
        "BAND_MAX": "as HOT_H with P_d = P_d,band,max",
    },
    "margin_rule": {
        "source": src(S_DBF1, "/items", "DBF1-TH-03 {margin_K 50, heat_load_factor 1.2}; owner row 86 (H1F-TH-01); HC-06 " + S_GATES),
        "hot": "PASS iff max over the governing hot cases of T_node (computed with 1.2 x heat loads) <= T_limit - 50 K (A9-07 REV-40 / REV-45 interpretation, " + S_A907 + ")",
        "cold": "nodes with a registered lower limit: T_min over the governing cold cases (computed with loads / 1.2, or 0 non-operating) >= T_lower (operating limit in TC5, non-operating limit in TC6); a shortfall is a heater requirement (sized below), not a FAIL",
        "limit_classes": {
            "SOURCED_GUIDE": "a cited supplier / guide value (NOT_VALIDATED): PASS / FAIL as above",
            "NECESSARY_CEILING": "a physical ceiling (Curie), not a usable limit: PASS means the necessary condition holds; the usable limit stays an EM verification item",
            "DERATED_ELECTRONICS": "EEE-INST-002 derated value: PASS / FAIL as above",
            "ASSUMED_FROM_MEMORY": "a selected engineering assumption (verify): PASS / FAIL as above, flagged",
            "REQUIREMENT_ONLY": "no admissible limit: output the required continuous-use capability T_max + 50 K (an EM / materials verification requirement); FAIL only when it exceeds a registered absolute ceiling",
        },
        "coatings": "every exterior coated node also outputs the required coating capability T_max + 50 K (H1F-MA-06)",
        "coated_nodes": COATED_NODES,
        "spacecraft_interface": "Q_sc = conduction into B_SC at T_SC,hot; compared with the owner provisional allocation 50 W governing / 100 W ceiling / 25 W stretch (H1F-TH-02, " + S_H1F + " /parameters/63)",
    },
    "limits": LIMITS,
    "design_levers": {
        "rule": "frozen-topology design completion (values not in DBF-1; no DCR): R_HALL area A_RH and the back-plate doubler conductance G_RH",
        "grid": {"A_RH_m2": [0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40], "G_RH_W_K": [2.0, 5.0, 10.0]},
        "evaluation": "steady TC1 and TC3 at every grid point",
        "feasible": "every H-1 node with a non-REQUIREMENT_ONLY limit (walls, poles, back plate, coils) PASSES in TC1 and TC3",
        "selection": "the feasible point with the smallest A_RH, then the smallest G_RH; confirmed in TC2 and TC4; if a confirmation fails, the next feasible point in the same order; if no point is feasible, the point that maximises the minimum H-1 margin (T_limit - 50 K - T) over the grid (ties: smaller A_RH, then smaller G_RH) is carried and the H-1 verdicts are FAIL where they fail",
    },
    "allowables": {
        "method": "bisection (60 iterations or 0.01 W) on one load scale at the selected design, TC1 environment (steady), every other input fixed; the allowable is the largest value with T_node <= T_limit - 50 K (REQUIREMENT_ONLY nodes: not computed); a non-converged or OUT_OF_DOMAIN run counts as above the limit",
        "AL-PD": "per H-1 limited node: P_d with the HOT_H fractions at V_d,min (I_d and the return heat scale with P_d), coils and ICP fixed, x 1.2; search [0, 3000] W",
        "AL-PFWD": "per ICP limited node (N_VESSEL, N_MATCH): P_fwd under HOT_I, x 1.2; search [0, 3000] W",
        "AL-PLUME": "per ICP limited node: Q_hall_plume_to_icp_W added to HOT_H with the input partition, x 1.2; search [0, 2000] W",
        "AL-RETURN": "per ICP limited node: Q_hall_return_to_icp_W under HOT_H (value replacing I_d E_return), x 1.2; search [0, 2000] W",
    },
    "sensitivities": {
        "rule": "non-governing; TC1 at the selected design with one input changed; reported raw for the DCR / design discussion; never used to select or to pass",
        "list": {
            "SENS-WALL-LO": "f_walls = lower analog (0.0439)",
            "SENS-ANODE-LO": "f_anode = lower analog (0.0206)",
            "SENS-CORE-ARMCO": "L_PI_BP k = MAT.armco.k (pure iron instead of FeCo-2V)",
            "SENS-HC-LO": "the folded joints (L_PI_BP, L_PO_BP) and the wall-support contacts (L_WI_BP, L_WO_BP) at 155 W/(m^2 K) (H25-30 lower; the coil contacts are already 155)",
            "SENS-HC-HI": "every contact (coil contacts, folded joints, wall supports) at 3100 W/(m^2 K) (H25-30 upper); a D-02 refusal is reported raw",
            "SENS-GAN-LO": "L_AN_BP = 0.55 W/K (H25-31 midpoint)",
            "SENS-COIL-CAP": "coils at the MC-1 capability 403 G (H2-1 case values without the band scaling)",
            "SENS-RETURN-HI": "E_return = 93.8 V: the largest analog ion-collector fall |V_K| (Takahashi Fig. 4a via P8 EV-12, Ar, V_D 260 V)",
            "SENS-TSC-20": "T_SC = 293.15 K", "SENS-TSC-40": "T_SC = 313.15 K",
        },
        "overrides": SENS_OVERRIDES,
        "icd_rule": "SENS-TSC-20 / SENS-TSC-40 with TC1 (T_SC 60 degC) are the SCI-A sensitivity of the closure-state rule; they are also run for TC3",
    },
    "boundary_units": {
        "rule": "units outside the NP-THERMAL control volume (EB-02): steady one-node rejection requirement on a dedicated zenith-facing radiator (Z-93 class) or a host conductance; Q_hot = 1.2 x dissipation, Q_cold = dissipation / 1.2 (operating) or 0 (non-operating)",
        "radiator_area": "A_req = Q_hot / (eps sigma T_d^4 - q_abs,hot), T_d = T_limit - 50 K, q_abs,hot = the orbit-average absorbed flux of a zenith panel, max over the hot BSTAR / B0 orbits at 180 km (the units carry enough mass for the orbit average; verify)",
        "heater": "P_heater = max(0, A_req (eps sigma T_low^4 - q_abs,cold) - Q_cold) with q_abs,cold = orbit-average zenith-panel flux of the cold B0 orbit at 230 km; T_low = operating (TC5 loads) or non-operating (0 W) lower limit",
        "units": {
            "PPU": {"dissipation": "P_d (1/eta_d - 1) + P_mag (1/eta_mag - 1) + P_hk (1/eta_hk - 1) + P_valve (1/eta_valve - 1)",
                    "upper_limit_C": 80.0, "lower_operating_C": -20.0, "lower_nonoperating_C": -40.0,
                    "limit_basis": "baseplate continuous-use limit = EEE-INST-002 S1 Table 4 derated junction 110 degC (150 degC part: min(0.8 x 150, 125, 150 - 40)) minus an assumed 30 K junction-to-baseplate rise (verify) (H2-5 PPU allowable form, " + S_H25 + " /limits); lower limits selected from memory (verify)", "class": "DERATED_ELECTRONICS"},
            "RF_GENERATOR": {"dissipation": "P_fwd (1/eta_RF - 1) + P_refl (B_PPU_RF RF_SOURCE booking, TK-01 + TK-02)", "upper_limit_C": 80.0, "lower_operating_C": -20.0, "lower_nonoperating_C": -40.0, "limit_basis": "as PPU", "class": "DERATED_ELECTRONICS"},
            "COMPRESSOR_MOTOR": {"dissipation": "P_compressor,el / eta_drive (whole electrical input booked as heat at the unit; H2-5 COMP basis)",
                                 "upper_limit_C": 180.0, "limit_basis": "IEC 60085 class 180 (H) winding insulation (" + S_LIM + " iec60085_thermal_classes) selected for the motor (assumed class; bearings / lubricant limit not sourced, verify)", "class": "ASSUMED_FROM_MEMORY",
                                 "host_conductance": "G_req = Q_hot / (T_d - T_SC,hot) when rejected into the host (REFERENCE_PENDING_ICD)", "flag": "compressor dissipation from DBF1-IN-08 (current DBF-1 compressor); to be updated from DCR-001 (lane L-INTAKE-DCR001)"},
        },
    },
    "materials_screening": {
        "source": src(S_MATG),
        "rule": "P8 DA-06 necessary screening ceilings (supplier oxidation-data temperature minus 50 K; never a validated limit). The P7 hot-case temperature (max over TC1-C4, 1.2 x loads) is compared with each ceiling directly (the 50 K is already inside the ceiling); the P8 registered DCR triggers are evaluated on that temperature and reported; a fired trigger makes the item DCR REQUIRED (it names its DBF-1 items)",
        "ceilings_C": {
            "H1_ANODE": {"IN600 (CAND-02A, primary, DBF1-MAT-01)": 930.0, "IN601 (CAND-03A, backup, DBF1-MAT-02)": 1150.0},
            "N_COLLECTOR": {"IN600 (CAND-02A, primary, DBF1-MAT-03)": 930.0, "IN601 (CAND-03A, backup, DBF1-MAT-03)": 1150.0},
            "H1_WALL_IN": {"BN-SiO2 HeBoSint CL-S 200": 850.0, "BN-SiO2 Combat M26 (distributor sheet)": 950.0, "BN HeBoSint PL 100": 850.0, "BN Combat AX05 (distributor sheet)": 800.0},
            "H1_WALL_OUT": {"BN-SiO2 HeBoSint CL-S 200": 850.0, "BN-SiO2 Combat M26 (distributor sheet)": 950.0, "BN HeBoSint PL 100": 850.0, "BN Combat AX05 (distributor sheet)": 800.0},
        },
        "dcr_triggers": [
            {"id": "MAT-TRIG-AN-930", "node": "H1_ANODE", "above_C": 930.0, "action": "DCR swapping primary and backup (DBF1-MAT-01 / DBF1-MAT-02)", "source": src(S_MATG, "/gates/5/dcr_trigger")},
            {"id": "MAT-TRIG-AN-1150", "node": "H1_ANODE", "above_C": 1150.0, "action": "DCR on DBF1-MAT-02 and the anode heat path (A9H-ANODE-02)", "source": src(S_MATG, "/gates/19/dcr_trigger")},
            {"id": "MAT-TRIG-COL-930", "node": "N_COLLECTOR", "above_C": 930.0, "action": "DCR swapping primary and backup in DBF1-MAT-03", "source": src(S_MATG, "/gates/12/dcr_trigger")},
            {"id": "MAT-TRIG-COL-1150", "node": "N_COLLECTOR", "above_C": 1150.0, "action": "DCR on DBF1-MAT-03 and the collector thermal path", "source": src(S_MATG, "/gates/26/dcr_trigger")},
            {"id": "MAT-TRIG-WALL-850", "node": "H1_WALL_IN", "above_C": 850.0, "action": "the grade within DBF1-MAT-04 or the thermal path changes by DCR (CL-S 200 ceiling)", "source": src(S_MATG, "/gates", "BNSIO2-WALL-THERMAL dcr_trigger")},
        ],
        "thermal_cycling": {"N_cycles_bound": 17928, "radial_mismatch_mm_per_100K": [0.0488, 0.0667], "source": src(S_MATG, "/analyses/4"),
                            "report": "per node the hot / cold range (max over TC1-C4, min over TC5 / TC6) and the anode-to-outer-wall radial differential growth = mismatch rate x (T_anode - T_wall_out) at the hot case and over the hot / cold swing"},
    },
    "closure_state_rule": {
        "precedence": "DCR REQUIRED > FUNDAMENTAL NON-CLOSURE > BLOCKED BY SPECIFIC MISSING EVIDENCE > REFERENCE/ICD DEPENDENT > FROZEN FOR EM > CLOSED",
        "DCR REQUIRED": "a P8 materials DCR trigger fires (materials_screening), or a node with a registered limit FAILS in a governing hot case at the selected design, and either it FAILS at every design-lever grid point (TC1 / TC3) or no grid point is feasible and confirmed: the failure cannot be closed by a non-DBF-1 value inside the frozen topology; the record names the DBF-1 items whose change could close it with the quantitative allowable (AL-PD / AL-PFWD) and drafts the DCR request (the DCR itself is registered by the coordinator per DCR_PROCESS.md)",
        "FUNDAMENTAL NON-CLOSURE": "a REQUIREMENT_ONLY node's required capability exceeds its registered absolute ceiling (material solidus) at the selected design",
        "BLOCKED BY SPECIFIC MISSING EVIDENCE": "a governing case cannot be evaluated (non-CONVERGED run status other than a property-range OUT_OF_DOMAIN treated as above-limit)",
        "REFERENCE/ICD DEPENDENT": "every node passes or carries a requirement, but a verdict changes across the SCI-A sensitivity (T_SC 20 / 40 / 60 degC) or Q_sc exceeds the 50 W governing allocation",
        "FROZEN FOR EM": "every limited node passes; the remaining items are EM verification requirements (REQUIREMENT_ONLY capabilities, coating capabilities, necessary ceilings, assumed limits, allowable-bounded parametric loads)",
        "CLOSED": "not reachable in this record: the model is NOT_VALIDATED and every case is PARAMETRIC",
    },
    "outputs": {
        "record": "docs/closure/thermal/thermal_closure_v1.json (+ .md): per node and governing case T, limit, margin, verdict; selected A_RH / G_RH; allowables; required capabilities; boundary-unit radiator areas and heaters; Q_sc; sensitivities; closure state; run provenance (rust commit, input sha256, case document sha256)",
        "statement": "docs/closure/statements/P7_thermal.md",
        "harness": "abep-assess binary abep-assess-thermal-closure --inputs <load input file> --out <record>",
    },
    "rerun_rule": "a new load-input version (power ledger from L-POWER-ICD, compressor from DCR-001) is run through the identical harness and this preregistration and writes thermal_closure_v<N>.json; a change of geometry, topology, limits or the method needs a new preregistration version",
    "check_values": {
        "F_anode_to_exit": r9(F_an_exit), "F_disc_disc_bore": r9(F_dd), "G_L_WI_BP_W_K": r9(G_wi), "G_L_WO_BP_W_K": r9(G_wo),
        "r_core_m": r9(r_core), "A_core_m2": r9(A_core), "L_core_eff_m": r9(L_core_eff),
        "F_ICP_UP_to_SPACE": r9(1 - sum(up_af.values()) / A_icp_up),
    },
}

# ------------------------------------------------------------------------------------------------ load inputs v1
B_RATIO_HOT = (268.6 / 403.0) ** 2
B_RATIO_COLD = (69.93 / 260.5) ** 2


def li(value, units, source, ec, uncertainty, label=None):
    d = {"value": r9(value) if isinstance(value, float) else value, "units": units, "source": source, "evidence_class": ec, "uncertainty": uncertainty}
    if label:
        d["label"] = label
    return d


PEND_PWR = "REGISTERED_ASSUMPTION_PENDING_L-POWER-ICD"
inputs = {
    "schema": "abep_closure_thermal_load_inputs_v1",
    "id": "P7-THERMAL-LOAD-INPUTS-v1",
    "version": 1,
    "prereg": "docs/closure/thermal/thermal_cases_prereg_v1.json",
    "status": "REGISTERED_ASSUMPTIONS (power ledger L-POWER-ICD and DCR-001 compressor not yet available)",
    "discharge": {
        "P_d_band_W": li([650.0, 1350.0], "W", src(S_DBF1, "/items", "DBF1-H1-06"), "owner-allocation", "band ends"),
        "V_d_band_V": li([180.0, 350.0], "V", src(S_DBF1, "/items", "DBF1-H1-05"), "owner-allocation", "band ends"),
        "P_d_hot_W": li(1050.0, "W", src(S_DBF1, "/items", "DBF1-PWR-04 HALL_AND_ELECTRON_SOURCE 1050 W at P_common 300 W"), ASSUMED,
                        "allocation bound: the whole Hall + electron-source envelope attributed to the discharge, lossless (conservative; the ICP and conversion losses lower the attainable P_d)", PEND_PWR),
        "f_anode_hot": li(30.0 / 180.0, "-", src(S_H25, "/design_parameters", "H25-04 upper: EXT-MAZOUFFRE2005 30 eV per electron / V_d,min 180 V"), INFERRED, "xenon analog; air value unknown"),
        "f_anode_cold": li(0.0206, "-", src(S_H25, "/design_parameters", "H25-04 lower: EXT-MYERS2016 Table 3"), INFERRED, "xenon analog"),
        "f_walls_hot": li(0.15, "-", src(S_H25, "/design_parameters", "H25-05 upper: EXT-MARTINEZ2014 13 +/- 2 %"), INFERRED, "xenon analog"),
        "f_walls_cold": li(0.0439, "-", src(S_H25, "/design_parameters", "H25-05 lower: EXT-MYERS2016"), INFERRED, "xenon analog"),
        "wall_inner_share": li(r_in / (r_in + r_out), "-", "channel-face area ratio r_in / (r_in + r_out) (assumed uniform wall flux)", ASSUMED, "producer split TBD (HK-04)"),
        "f_pole_hot": li(0.01448, "-", src(S_H25, "/design_parameters", "H25-06 upper: EXT-MYERS2016 inner front pole"), INFERRED, "shielded analog"),
        "f_pole_cold": li(0.0, "-", src(S_H25, "/design_parameters", "H25-06 lower"), INFERRED, "unshielded bound"),
        "E_return_hot_V": li(30.0, "V", "selected engineering assumption: the ICP ion collector receives the Hall discharge current (P8 assumption A-ICP-01, " + S_MATG + ") at the same per-charge energy as the upper anode analog (EXT-MAZOUFFRE2005 30 eV); the analog collector fall spans 2.7-93.8 V (P8 EV-12, Takahashi Fig. 4a, Ar); verify by P1 / ICD ICP-43 calorimetry", ASSUMED, "2.7-93.8 V analog span; SENS-RETURN-HI and AL-RETURN reported"),
        "E_return_cold_V": li(0.0, "V", "cold-case lower bound (no return heat)", ASSUMED, "bound"),
        "plume_partition": li({"N_VESSEL": 0.25, "N_COLLECTOR": 0.5, "N_HOUSING": 0.2, "N_MOUNT": 0.05}, "-", "assumed split of intercepted plume power (bore-dominated); K-P3-RAYS with a measured angular distribution supersedes it (P3-H-03)", ASSUMED, "verify"),
    },
    "coils": {
        "hot_inner_W": li(27.84 * B_RATIO_HOT, "W", src(S_H21, "/coil_design/cases/2/coils/inner/chosen/P_kulgrid_538C_W", "27.84 W at 403 G x (268.6 / 403)^2 to the DBF1-BZ-02 band upper end; FIXED_POWER at the 538 degC class temperature (conservative)"), MODEL, "lumped magnetics; FEMM pending (DBF1-BD-05)"),
        "hot_outer_W": li(58.4 * B_RATIO_HOT, "W", src(S_H21, "/coil_design/cases/2/coils/outer/chosen/P_kulgrid_538C_W", "58.4 W at 403 G x (268.6 / 403)^2"), MODEL, "lumped magnetics"),
        "cap_inner_W": li(27.84, "W", src(S_H21, "/coil_design/cases/2/coils/inner/chosen/P_kulgrid_538C_W"), MODEL, "MC-1 capability case (SENS-COIL-CAP)"),
        "cap_outer_W": li(58.4, "W", src(S_H21, "/coil_design/cases/2/coils/outer/chosen/P_kulgrid_538C_W"), MODEL, "MC-1 capability case"),
        "cold_inner_W": li(0.3652 * B_RATIO_COLD, "W", src(S_H21, "/coil_design/cases/0/coils/inner/chosen/P20_W", "RP-1 f_NI 1 at 20 degC x (69.93 / 260.5)^2 to the band lower end"), MODEL, "lumped magnetics"),
        "cold_outer_W": li(0.9236 * B_RATIO_COLD, "W", src(S_H21, "/coil_design/cases/0/coils/outer/chosen/P20_W", "RP-1 f_NI 1 at 20 degC x (69.93 / 260.5)^2"), MODEL, "lumped magnetics"),
        "trim_W": li(0.0, "W", src(S_MP5, "/power/configurations/hall_icp_neutralizer/slots", "hall_magnet_trim: 0 W explicit when unpowered"), ASSUMED, "trim NI TBD (H1F-CO-07)"),
    },
    "icp": {
        "P_fwd_anchor_W": li(200.0, "W", src(S_P1, "/anchor_check", "TK-21 Takahashi 200 W forward"), ANALOG, "published analog at ~1 A; H-1 need not evaluated (BD-06)"),
        "P_fwd_max_W": li(500.0, "W", src(S_DBF1, "/items", "DBF1-RF-02 forward envelope upper end"), ASSUMED, "envelope end"),
        "eta_RF": li(0.6, "-", src(S_H24, "/design_parameters", "H24-14 rf_source chain efficiency 0.6-0.92, lower end"), INFERRED, "0.6-0.92", PEND_PWR),
        "P_refl_frac": li(0.0, "-", src(S_P1, "/anchor_check", "TK-22 reflected 0 W"), ANALOG, "meter resolution not stated"),
        "Q_line_frac": li(0.0, "-", "no in-module line segment registered (co-located match); coax loss outside the module (assumed)", ASSUMED, "verify (P2)"),
        "Q_match_frac": li(0.05, "-", "match loss 5 % of P_fwd (assumed; adjustable L-network class, from memory, verify)", ASSUMED, "verify (P2 impedance map)"),
        "P_matching_DC_W": li(5.0, "W", "match actuator / controller DC 5 W (assumed; adjustable match DBF1-RF-03)", ASSUMED, "verify"),
        "eta_p": li(0.1, "-", src(S_P1, "/anchor_check", "TK-26 eta_p ~ 0.1"), ANALOG, "authors' estimate"),
        "abs_split": li({"plasma_wall": 0.6, "radiation": 0.2, "extraction": 0.1, "outflow_upstream": 0.05, "outflow_downstream": 0.05}, "-", "assumed split of the absorbed RF power", ASSUMED, "verify (NP-ICP v2)"),
        "plasma_wall_node_shares": li({"N_VESSEL": 0.5, "N_COLLECTOR": 0.5}, "-", "assumed (producer TK-07 shares TBD)", ASSUMED, "verify"),
        "coil_ohmic_split": li({"N_ANTENNA": 0.4, "N_COLLECTOR": 0.4, "N_HOUSING": 0.2, "N_MOUNT": 0.0}, "-", "assumed TK-06 split; Takahashi attributes most RF power to electrode eddy heating (TK-27 context)", ASSUMED, "verify (P1-S2 unlit heating)"),
        "f_rad": li({"N_VESSEL": 0.3, "N_ANTENNA": 0.0, "N_COLLECTOR": 0.3, "N_HOUSING": 0.0, "H1_POLE_IN": 0.05, "H1_POLE_OUT": 0.05, "EXPORT": 0.3}, "-", "assumed f_rad", ASSUMED, "verify"),
        "f_up": li({"H1_POLE_IN": 0.2, "H1_POLE_OUT": 0.3, "H1_WALL_IN": 0.1, "H1_WALL_OUT": 0.1, "H1_ANODE": 0.05, "N_MOUNT": 0.0, "N_HOUSING": 0.1, "EXPORT": 0.15}, "-", "assumed RX-H1-FACE f_up", ASSUMED, "verify (K-P3-RAYS)"),
    },
    "ppu": {
        "eta_d": li(0.8583, "-", src(S_H24, "/design_parameters", "H24-05 0.8583-0.915, lower end"), "digitized", "analog SSEP sub-kW PPU", PEND_PWR),
        "eta_mag": li(0.6, "-", src(S_H24, "/design_parameters", "H24-09"), ASSUMED, "analog minimum", PEND_PWR),
        "P_hk_out_W": li(30.0, "W", src(S_H24, "/design_parameters", "H24-22 (30 W output rating)"), ASSUMED, "screening", PEND_PWR),
        "eta_hk": li(0.7, "-", src(S_H24, "/design_parameters", "H24-11"), ASSUMED, "analog minimum", PEND_PWR),
        "P_valve_out_W": li(10.0, "W", "valve-driver output 10 W (assumed, verify)", ASSUMED, "verify", PEND_PWR),
        "eta_valve": li(0.8, "-", src(S_H24, "/design_parameters", "H24-10"), ASSUMED, "analog minimum", PEND_PWR),
    },
    "compressor": {
        "P_el_max_W": li(11.125100048512362, "W", src(S_DBF1, "/items", "DBF1-IN-08 max over covered scenarios (cll_a0.5)"), MODEL, "PARAMETRIC_SENSITIVITY", "FLAGGED_FOR_UPDATE_FROM_DCR-001 (L-INTAKE-DCR001)"),
        "eta_drive": li(0.85, "-", "motor-drive efficiency 0.85 (assumed; H24-12 TBD), verify", ASSUMED, "verify", PEND_PWR),
    },
}

# ------------------------------------------------------------------------------------------------ write
def dump(obj, rel):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    data = (json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()
    with open(p, "wb") as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    h1 = dump(prereg, "docs/closure/thermal/thermal_cases_prereg_v1.json")
    h2 = dump(inputs, "docs/closure/thermal/thermal_load_inputs_v1.json")
    lock = {"schema": "abep_closure_prereg_lock_v1", "id": "P7-THERMAL-CASES-PREREG-LOCK-v1",
            "files": {"docs/closure/thermal/thermal_cases_prereg_v1.json": h1,
                      "docs/closure/thermal/thermal_load_inputs_v1.json": h2,
                      "docs/closure/thermal/build_thermal_cases_prereg_v1.py": sha("docs/closure/thermal/build_thermal_cases_prereg_v1.py")},
            "rule": "committed alone before any production case; the harness refuses a prereg whose sha256 differs; a load-input v1 change is a new input version, never an edit"}
    dump(lock, "docs/closure/thermal/thermal_cases_prereg_lock_v1.json")
    print(h1, h2)
