"""DCR-DBF1-001 compressor / feed mass-closure design v5 (owner instruction 2026-10-10, after v4 at c68fdca). Deterministic, < 1 s.
1) AIR sizing flow from the registered RFP clauses + A9.40 (no relaxation, no imposed 25 mN AIR mapping).
2) Feed co-design plenum -> isolation valve -> metering valve -> manifold -> equal-path branch tree -> annular distributor -> H1
   channel (H1 frozen), with a physical uniformity rule instead of p_dist >= 3 p_anode; lowest controllable plenum pressure.
3) Integrated contra-rotating compressor (front free-molecular rows -> transitional booster rows -> Holweck section on the same two
   shafts), every row from explicit rotor kinematics with the repository row model (abep_sim/compressor.py / abep-gaspath:
   ln K0 = kK u / c_bar, S = kS u A, loaded K = K0 - (K0 - 1) Q / (S p_in); drag ln K0 = 2 u L xi / (c_bar h), S0 = xi u h w / 2).
4) Component compressor CBE, governed mass convention (A9.26 MGA 20 % new design), complete mass roll-up (other lines from v4).
PROPOSAL-LEVEL / PARAMETRIC / NOT_VALIDATED."""
import json, math
from pathlib import Path
k_B, amu = 1.380649e-23, 1.66053906660e-27
M = 24 * amu                                                   # same compressed-air mean mass as v2-v4
def Q(mdot, T): return mdot * k_B * T / M                     # Pa m3/s
def cbar(T): return math.sqrt(8 * k_B * T / (math.pi * M))
LAMBDA_P = 6.8e-3                                             # Pa m, air ~300 K (v4)
T_C, T_H = 300.0, 500.0                                       # cold feed side; distributor / channel (assumed, as v4)
def W_tube(L, d): return 1 / (1 + 0.75 * L / d)               # Clausing-type transmission (-> 4d/3L long-tube limit)
def C_tube(d, L, T): return math.pi * d * d / 4 * cbar(T) / 4 * W_tube(L, d)
def C_duct(d, L, T): return math.pi / 12 * d ** 3 / L * cbar(T)   # duct (wall) resistance only; entrances added at contractions
def C_orif(A, T): return A * cbar(T) / 4

# ---------- 1. AIR sizing flow ----------
U_DES, ETA_DES, U_CONS, ETA_CONS = 26.8e3, 0.27, 22.0e3, 0.22   # A9.40: 26.8 km/s design/reference basis, 22 km/s sensitivity
FLOWS = {"SIZING_AIR_12mN_design_basis": 12e-3 / U_DES, "AIR_12mN_22kms_sensitivity": 12e-3 / U_CONS, "AIR_high_capability_1.33": 1.33e-6}
MD_SIZ = FLOWS["SIZING_AIR_12mN_design_basis"]
sizing_basis = dict(
    rfp=["RFP-P18-06 thrust 12 mN to 25 mN (from expected drag to compensate); no propellant split (DISC-07)",
         "RFP-P18-08 / RFP-P17-05 ambient air AND Xe; Xe 'an extra input system to take care any problems on board' (DISC-06)",
         "RFP-P18-05 intake decided by air density, solar activity and altitude", "RFP-P18-10 < 1500 W", "RFP-P18-11 < 40 kg"],
    a9_40=["AIR 12 mN is the nominal atmospheric drag-compensation point (compressor ON, ~1.15 kW)",
           "25 mN is a capability point established in Xe mode (compressor OFF) at <= ~1450 W",
           "the 196 states are a conservative verification set; AIR uses a density / altitude window; outside it Xe",
           "26.8 km/s is the design / reference air-Hall basis; 22 km/s is a sensitivity / risk case"],
    mandatory_air_point="12 mN AIR inside the admissible density / altitude window (RFP lower bound of the thrust range, A9.40 power gate)",
    nominal_air_operation="drag compensation T >= D in the AIR window; with host C_D A 0.50 m2 the window is chosen where 12 mN covers drag",
    system_12_25mN="met as a system: 12 mN AIR + 25 mN capability in Xe; the RFP does not map 25 mN to air",
    xe_contingency="25 mN in Xe, compressor OFF, <= 1450 W design ceiling",
    sizing_flow_mg_s=MD_SIZ * 1e6,
    sizing_flow_rule="12 mN / 26.8 km/s = Hall anode flow (ICP dedicated flow 0, DBF1-ICP-05 G-REUSE)",
    carried_not_guaranteed={"22 km/s sensitivity 0.545 mg/s": "checked against the selected plenum and compressor; reported, not a sizing guarantee",
                            "1.33 mg/s high AIR capability": "sensitivity only; needs a higher plenum setpoint and compressor loading (reported)"})

# ---------- 2. feed co-design (H1 frozen: d_mean 70 mm, h 12 mm, L 103.2 mm) ----------
D_M, H_CH, L_CH = 0.070, 0.012, 0.1032
W_CH = 0.30                                                   # annular-slot transmission at L/h 8.6 (v4 value; verify)
C_CH = math.pi * D_M * H_CH * cbar(T_H) / 4 * W_CH
# annular distributor ring behind the anode face: radial 12 mm (= channel width) x axial 20 mm, N_IN equal-path inlets
RING_W, RING_H, N_IN = 0.012, 0.020, 8
A_R, P_R = RING_W * RING_H, 2 * (RING_W + RING_H)
cL_ring = 4 / 3 * cbar(T_H) * A_R ** 2 / P_R                 # Knudsen duct conductance x length (m4/s); molecular = lower bound
S_ARC = math.pi * D_M / (2 * N_IN)                            # inlet-to-midpoint arc
UNIF = 0.05                                                   # +/-5 % azimuthal anode-flux uniformity (assumed H1 requirement; verify)
R_U = 1 / (2 * UNIF)                                          # outlet dp >= 10 x ring peak-to-peak dp (flux ~ p_ring - p_anode)
def ring_dp(QH): return (QH / (2 * N_IN)) * S_ARC / (2 * cL_ring)   # uniform withdrawal along the arc
# outlet holes through a 2 mm anode face, 3 mm diameter. Highest conductance allowed by the anode face: open area <= 50 % of the
# channel base (OPEN_MAX, assumed: face integrity / plasma back-streaming); the uniformity rule is then checked, not forced.
D_HO, T_HO, OPEN_MAX = 0.003, 0.002, 0.50
c_hole = math.pi * D_HO ** 2 / 4 * cbar(T_H) / 4 * W_tube(T_HO, D_HO)
N_HOLES = math.floor(OPEN_MAX * math.pi * D_M * H_CH / (math.pi * D_HO ** 2 / 4)); C_OUT = N_HOLES * c_hole
OPEN_FRAC = N_HOLES * math.pi * D_HO ** 2 / 4 / (math.pi * D_M * H_CH)
UNIF_RATIO = (Q(MD_SIZ, T_H) / C_OUT) / ring_dp(Q(MD_SIZ, T_H))
assert UNIF_RATIO >= R_U, UNIF_RATIO
# equal-path branch tree 1 -> 2 -> 4 -> 8 (symmetry gives equal inlet flows; no uniformity dp needed upstream).
# Series rule (Santeler): duct wall resistances + an entrance (orifice) penalty only where the flow area contracts.
TREE = [(2, 0.028, 0.06, T_C), (4, 0.022, 0.05, T_C), (8, 0.018, 0.03, T_H)]   # (count, d, L, T)
C_TREE = [n * C_duct(d, L, T) for n, d, L, T in TREE]
A_MAN = math.pi * 0.040 ** 2 / 4
def contraction(A_up, A_dn, T): return 1 / max(1 / C_orif(A_dn, T) - 1 / C_orif(A_up, T), 1e-30) if A_dn < A_up else float("inf")
C_CONTR = contraction(A_MAN, 2 * math.pi * 0.028 ** 2 / 4, T_C)   # manifold -> 2 x 28 mm (the only contraction in the tree)
C_MAN = C_duct(0.040, 0.10, T_C)                              # main manifold 40 mm x 100 mm, valve -> tree
C_ISO = 0.6 * C_orif(A_MAN, T_C)                              # isolation (latch) valve, 40 mm bore, seat/poppet transmission 0.6 (assumed)
C_V_FULL = 0.10                                               # metering valve full-open conductance (~30 mm effective bore)
AUTH = 0.25                                                   # control authority: full-open capacity >= 1.25 x demanded flow
BAND = 0.05                                                   # plenum pressure control band +/-5 %
def chain(md, Cv):
    qc, qh = Q(md, T_C), Q(md, T_H)
    d = {"channel (p_anode)": qh / C_CH, "distributor outlet holes": qh / C_OUT, "distributor ring (azimuthal, max)": ring_dp(qh)}
    for (n, dd, L, T), c in zip(TREE, C_TREE):
        d[f"branch {n} x {dd*1e3:.0f} mm x {L*1e3:.0f} mm"] = (qh if T == T_H else qc) / c
    d["contraction manifold -> branch 2"] = qc / C_CONTR
    d["main manifold 40 mm x 100 mm"] = qc / C_MAN; d["isolation valve 40 mm"] = qc / C_ISO; d["metering valve"] = qc / Cv
    return d
def p_required(md):                                           # valve fully open, all series elements
    return sum(chain(md, C_V_FULL).values())
P_MIN_CTRL = (1 + AUTH) * p_required(MD_SIZ)                  # lowest plenum pressure that still leaves 25 % flow authority
P_SET = P_MIN_CTRL / (1 - BAND)                               # setpoint with the -5 % band edge still >= P_MIN_CTRL
feed = {}
for k, md in FLOWS.items():
    full = chain(md, C_V_FULL); p_req = sum(full.values())
    Cv_op = Q(md, T_C) / (P_SET - (p_req - Q(md, T_C) / C_V_FULL)) if P_SET > p_req else None
    feed[k] = dict(mdot_mg_s=md * 1e6, dp_full_open_Pa={a: round(b, 4) for a, b in chain(md, C_V_FULL).items()},
                   p_anode_Pa=full["channel (p_anode)"], p_distributor_Pa=full["channel (p_anode)"] + full["distributor outlet holes"] + full["distributor ring (azimuthal, max)"],
                   p_plenum_required_full_open_Pa=p_req, p_plenum_min_controllable_Pa=(1 + AUTH) * p_req,
                   met_at_setpoint=P_SET * (1 - BAND) >= p_req, valve_opening_at_setpoint=(Cv_op / C_V_FULL) if Cv_op else None)

# ---------- 3. integrated contra-rotating compressor ----------
KS, KK, XI = 0.20, 1.2, 0.6                                   # repository row / drag coefficients (abep_sim/compressor.py; T-1, uncited)
A_FACE, W_REV = 0.70, 1 / (1 + 0.75 * 20)
S_EFF1 = 2.0 * A_FACE * cbar(T_C) / 4 * W_REV                 # intake retention design (v2-v4): S_eff = 2 C_back -> 2/3 retention
R_T, U_TIP = 0.333, 300.0                                     # front rotor tip radius (v4 D 0.665 m); tip speed (v1 basis 250-350)
OMEGA = U_TIP / R_T; RPM = OMEGA * 60 / (2 * math.pi)
H_MIN = 0.005                                                 # minimum blade height (>= ~15 x 0.3 mm tip clearance)
NU_MIN = 0.30                                                 # hub-ratio floor (shaft-B hub drum / web)
PHI = 0.5                                                     # row loading target Q / (S_max p_in)
P_ADM = 0.1                                                   # admitted free-molecular limit for blade rows (EV-03)
R_HOLW = R_T + 0.004                                         # Holweck = OUTER surface of the shaft-A drum (drum skin 4 mm)
H_G, ELL_H, ALPHA, LAND = 0.0020, 0.040, math.radians(45.0), 0.15   # groove depth, axial length, helix angle, land fraction
def row_geom(S_need, u_prev_rel_factor):
    """Largest-radius row giving S_max = S_need with h >= H_MIN at radius <= R_T (constant-tip rows first, then step inward)."""
    # constant tip: A = pi R_T^2 (1 - nu^2), r_m = R_T (1 + nu)/2
    # constant tip radius (tip speed fixed); hub rises as the volume flow falls; floors nu >= NU_MIN and h >= H_MIN.
    # Rows never step inward (a smaller radius would lower the blade speed at the same rpm).
    nu_hmax = 1 - H_MIN / R_T
    for i in range(0, 10001):
        nu = NU_MIN + (nu_hmax - NU_MIN) * i / 10000
        A = math.pi * R_T ** 2 * (1 - nu ** 2); rm = R_T * (1 + nu) / 2; u = OMEGA * rm
        if KS * u * u_prev_rel_factor * A <= S_need or i == 10000:
            return (R_T, nu * R_T, A, rm, u)
def comp_run(md, p_target):
    q = Q(md, T_C); p = q / S_EFF1; rows = []; prev_u = 0.0; i = 0
    while i < 30:
        S_need = q / (p * PHI) if i else None
        if i == 0:                                            # row 1 fixed by the retention requirement: full tip annulus, hub 0.4
            nu = 0.4; A = math.pi * R_T ** 2 * (1 - nu ** 2); rm = R_T * (1 + nu) / 2; u = OMEGA * rm; urel = u
            g = (R_T, nu * R_T, A, rm, u)
        else:
            g = row_geom(S_need, 2.0); urel = g[4] + prev_u
        A, rm, u = g[2], g[3], g[4]
        h = g[0] - g[1]; kn = LAMBDA_P / (p * h)
        lnK0 = KK * urel / cbar(T_C)
        derate = 1.0 if p <= P_ADM else kn / (1 + kn)         # transitional derating ABOVE 0.1 Pa (assumed; not admitted)
        K0 = math.exp(lnK0 * derate); Smax = KS * urel * A
        K = K0 - (K0 - 1) * q / (Smax * p)
        if K <= 1.0:
            raise RuntimeError(f"row {i+1} does not compress (K {K:.3f})")
        po = p * K
        rows.append(dict(row=f"{'F' if po <= P_ADM * 1.0001 or p < P_ADM else 'B'}{i+1}", shaft="A" if i % 2 == 0 else "B",
                         r_tip_m=g[0], r_hub_m=g[1], blade_height_mm=h * 1e3, r_mean_m=rm, rpm=RPM, u_tip_m_s=OMEGA * g[0],
                         u_mean_m_s=u, u_rel_m_s=urel, annulus_m2=A, S_max_m3_s=Smax, p_in_Pa=p, p_out_Pa=po, K=K, K0=K0,
                         throughput_Pa_m3_s=q, Kn_in=kn, Kn_out=LAMBDA_P / (po * h),
                         domain="free molecular, admitted (<= 0.1 Pa)" if po <= P_ADM * 1.0001 else
                                ("transitional booster, NOT admitted; ln K0 derated by Kn/(1+Kn)" if p >= P_ADM else "crosses 0.1 Pa: booster rule applied to outlet")))
        p = po; prev_u = u; i += 1
        if p >= P_ADM and rm <= R_HOLW + 0.02 and False:
            break
        if p >= P_B_SWITCH:
            break
    holw = holweck(q, p, p_target)
    return rows, holw
def holweck(q, p, p_target):
    # helical grooves in a stationary Al band of the housing facing the OUTER surface of the shaft-A drum (shared rotor)
    u_h = OMEGA * R_HOLW; u_c = u_h * math.cos(ALPHA)
    W = 2 * math.pi * R_HOLW * math.sin(ALPHA) * (1 - LAND); L_unw = ELL_H / math.sin(ALPHA)
    S0 = XI * u_c * H_G * W / 2; K0 = math.exp(min(2 * u_c * L_unw * XI / (cbar(T_C) * H_G), 50.0))
    K = K0 - (K0 - 1) * q / (S0 * p)
    p_kn = LAMBDA_P / (0.5 * H_G)                             # outlet pressure at the drag-channel Kn >= 0.5 domain edge
    return dict(p_out_domain_limit_Pa=p_kn, p_out_deliverable_in_domain_Pa=min(p * max(K, 0.0), p_kn), stage="H Holweck (outer surface of the shaft-A drum, stationary grooved Al band in the housing)", r_m=R_HOLW, rpm=RPM,
                u_m_s=u_h, u_channel_m_s=u_c, helix_deg=math.degrees(ALPHA), groove_depth_mm=H_G * 1e3, axial_length_m=ELL_H,
                total_channel_width_m=W, unwrapped_length_m=L_unw, S0_m3_s=S0, ln_K0=math.log(K0), loading=q / (S0 * p),
                p_in_Pa=p, p_out_capability_Pa=p * max(K, 0.0), p_out_required_Pa=p_target, PR_required=p_target / p, PR_capability=max(K, 0.0),
                throughput_Pa_m3_s=q, Kn_in=LAMBDA_P / (p * H_G), Kn_out=LAMBDA_P / (p_target * H_G),
                domain="molecular-drag channel; repository drag-channel bound Kn >= 0.5 " + ("met" if LAMBDA_P / (p_target * H_G) >= 0.5 else "NOT met"),
                closes=min(K * p, p_kn) >= p_target and q / (S0 * p) < 1)
P_B_SWITCH = 0.45                                             # booster -> Holweck hand-over pressure (Holweck width must fit the drum)
ROWS, HOLW = comp_run(MD_SIZ, P_SET)
# check at the 22 km/s flow and the high-capability flow with the same machine (fixed geometry: re-evaluate loaded K)
def recheck(md):
    q = Q(md, T_C); p = q / S_EFF1; out = []
    for r in ROWS:
        h = r["blade_height_mm"] / 1e3; kn = LAMBDA_P / (p * h)
        der = 1.0 if p <= P_ADM else kn / (1 + kn)
        K0 = math.exp(KK * r["u_rel_m_s"] / cbar(T_C) * der); K = K0 - (K0 - 1) * q / (r["S_max_m3_s"] * p)
        if K <= 1: return dict(ok=False, failed_at=r["row"], K=K)
        p *= K
    h = holweck(q, p, P_SET)
    preq = (1 + AUTH) * p_required(md)
    return dict(p_booster_out_Pa=p, holweck_loading=h["loading"], p_plenum_deliverable_in_domain_Pa=h["p_out_deliverable_in_domain_Pa"],
                p_plenum_required_min_controllable_Pa=preq, closes=h["p_out_deliverable_in_domain_Pa"] >= preq and h["loading"] < 1)
recheck_out = {k: recheck(md) for k, md in FLOWS.items()}

# ---------- 4. compressor component CBE ----------
CFRP, AL, TI = 1600.0, 2700.0, 4430.0
def L(item, cbe, mga, basis, ev): return dict(item=item, cbe_kg=round(cbe, 3), mga=mga, mev_kg=round(cbe * (1 + mga), 3), basis=basis, evidence_class=ev)
rotor_rows = sum(r["annulus_m2"] for r in ROWS) * 1.74        # v3 basis: CFRP 0.5 mm blades, solidity 0.9, Al hub rings
n_rows = len(ROWS); ax_len = 0.015 * n_rows + 0.06            # row pitch 15 mm + Holweck band
r_aft = min(r["r_hub_m"] for r in ROWS)
drum_A = 2 * math.pi * R_T * ax_len * 1.0e-3 * CFRP           # shaft-A outer rotating drum carrying the A rows (CFRP 1.0 mm hoop)
drum_B = 2 * math.pi * 0.5 * (R_T * 0.4 + r_aft) * ax_len * 1.0e-3 * CFRP   # shaft-B inner conical drum (CFRP 1.0 mm)
spokes = 2 * 0.12                                             # two Ti spoke / web discs joining drums to shafts
holw_rotor = 2 * math.pi * R_HOLW * ELL_H * 0.002 * CFRP     # local drum thickening (+2 mm CFRP hoop) under the Holweck band
holw_stator = 2 * math.pi * (R_HOLW + 0.002) * ELL_H * 0.004 * AL - 2 * math.pi * R_HOLW * ELL_H * 0.8e-3 * CFRP   # 4 mm Al grooved band replacing CFRP shell
housing_A = 2 * math.pi * (R_T + 0.01) * ax_len + math.pi * (R_T + 0.01) ** 2 * 0.6   # cylinder + aft closure (partial)
housing = housing_A * 0.8e-3 * CFRP + 0.25                    # CFRP 0.8 mm + Al flanges / inserts
comp = [
  L(f"rotor blade rows: {n_rows} bladed rows, annulus sum {sum(r['annulus_m2'] for r in ROWS):.3f} m2 x 1.74 kg/m2", rotor_rows, 0.20, "geometry (v3 areal basis)", "model-derived"),
  L("rotating drums: shaft-A outer CFRP drum + shaft-B inner conical drum (1.0 mm) + 2 Ti web discs", drum_A + drum_B + spokes, 0.20, "geometry", "model-derived"),
  L("stators: none in the contra-rotating blade section (rows alternate between shafts); Holweck stator sleeve", holw_stator, 0.20, "geometry", "model-derived"),
  L(f"Holweck rotor: shared shaft-A drum, local +2 mm CFRP hoop under the {ELL_H*1e3:.0f} mm band", holw_rotor, 0.20, "geometry", "model-derived"),
  L("shafts: coaxial Ti inner shaft 16 mm + outer tube 30/26 mm, ~0.25 m", TI * 0.25 * (math.pi / 4) * (0.016 ** 2 + 0.030 ** 2 - 0.026 ** 2), 0.20, "geometry", "model-derived"),
  L("bearings: 4 hybrid-ceramic angular-contact (2 per shaft) + preload springs + housings + dampers", 4 * 0.04 + 0.20, 0.20, "estimate (small-bore bearing class; verify)", "assumed"),
  L("motors: 2 frameless BLDC (~0.05 N m, ~25 W each)", 2 * 0.20, 0.20, "estimate (frameless motor class; verify)", "assumed"),
  L("housing: stationary CFRP 0.8 mm shell + aft closure + Al flanges / inserts", housing, 0.20, "geometry", "model-derived"),
  L("drive electronics: one dual-axis sensorless BLDC drive (contra-rotation speed matching)", 0.35, 0.20, "estimate (verify)", "assumed"),
  L("isolation hardware: launch lock / caging (2 shafts) + 4 elastomer isolators", 0.30, 0.20, "estimate (verify)", "assumed"),
  L("sensors: 2 speed pick-offs, 3 RTDs, 1 accelerometer, inter-stage gauge", 0.08, 0.20, "estimate", "assumed"),
  L("mounts: brackets to intake shroud / module structure", 0.25, 0.20, "estimate", "assumed")]
comp_cbe = sum(x["cbe_kg"] for x in comp); comp_mev = sum(x["mev_kg"] for x in comp)
# kinematics checks: hoop / centrifugal growth at the Holweck and the outer drum
grow_holw = CFRP * HOLW["u_m_s"] ** 2 * R_HOLW / 140e9
grow_drum = CFRP * U_TIP ** 2 * R_T / 140e9
hoop_drum = CFRP * U_TIP ** 2 / 1e6

# ---------- power ----------
def fm_shear_power(p, u, A_wet): return 2 * p * u / (math.pi * cbar(T_C)) * u * A_wet     # free-molecular diffuse shear (upper estimate)
P_rows = sum(fm_shear_power(math.sqrt(r["p_in_Pa"] * r["p_out_Pa"]), r["u_rel_m_s"] / 2, 2 * 0.9 * r["annulus_m2"]) for r in ROWS)
P_holw = fm_shear_power(math.sqrt(HOLW["p_in_Pa"] * HOLW["p_out_required_Pa"]), HOLW["u_m_s"], 2 * math.pi * R_HOLW * ELL_H)
P_gas = Q(MD_SIZ, T_C) * math.log(P_SET / (Q(MD_SIZ, T_C) / S_EFF1))
P_bear = 4 * 1.0
P_shaft = P_rows + P_holw + P_gas + P_bear
P_elec = P_shaft / (0.85 * 0.90) + 5.0                        # motor 0.85, drive 0.90, drive quiescent 5 W
COMP_P = {"estimate": round(P_elec, 1), "allowance": round(2 * P_elec, 1)}
CH = 0.90 * 0.95
ND_air = {k: 428.0 + (v - 9.76) / 0.85 for k, v in COMP_P.items()}           # v3/v4 non-discharge bus basis
bus12 = {"reference": 12e-3 * U_DES / (2 * ETA_DES) / CH + ND_air["estimate"], "conservative": 12e-3 * U_CONS / (2 * ETA_CONS) / CH + ND_air["allowance"]}

# ---------- 5. complete mass ----------
v4 = json.loads(Path(__file__).with_name("dcr001_pressure_domain_closure_v4.json").read_text())
sub4 = dict(v4["bom_subtotals_mev_kg"]); sub = dict(sub4)
sub["AL-02 compressor"] = round(comp_mev, 3)
V_PLEN = 1.0 * Q(MD_SIZ, T_C) / P_SET                         # 1 s residence at sizing flow (v4 rule)
plen_vessel_cbe = 0.35 * (V_PLEN / 4.76e-3) ** (2 / 3) if V_PLEN > 4.76e-3 else 0.35   # v4 vessel 0.35 kg CBE at 4.8 L; scaled by area
feed_items = [L(f"plenum vessel {V_PLEN*1e3:.1f} L (thin Al/CFRP)", plen_vessel_cbe, 0.2, "geometry", "model-derived"),
              L("metering valves x2 (redundant), ~30 mm effective bore", 0.30, 0.2, "estimate", "assumed"),
              L("isolation valve 40 mm", 0.15, 0.2, "estimate", "assumed"),
              L("pressure sensors x2", 0.20, 0.2, "estimate", "assumed"),
              L("manifold 40 mm, branch tree 2/4/8 (thin SS), fittings", 0.25, 0.2, "geometry estimate", "assumed")]
sub["AL-03 plenum/feed"] = round(sum(x["mev_kg"] for x in feed_items), 3)
nonh = sum(sub.values()); nominal = nonh / 0.95; harness = nominal - nonh; dry = nominal * 1.1; wet = dry + 2.0
deficit = max(0.0, wet - 40.0)
rank = [dict(rank=1, line="AL-07 PPU", mev_kg=sub["AL-07 PPU"], basis="owner floor 5.0 x 1.2; largest single line; supplier / CAD evidence could replace the floor"),
        dict(rank=2, line="AL-08 Xe hardware", mev_kg=sub["AL-08 Xe hardware (single branch, 2 kg Xe)"], basis="XFC 1.02 kg measured; tank / plumbing / mount estimates"),
        dict(rank=3, line="AL-01 intake structure", mev_kg=sub["AL-01 intake"], basis="collimator + shroud geometry; shroud could share the compressor housing"),
        dict(rank=4, line="AL-10 structure / thermal", mev_kg=sub["AL-10 structure / thermal"], basis="owner allocation")]

out = dict(label="PROPOSAL-LEVEL / PARAMETRIC / NOT_VALIDATED", supersedes="v4 compressor / feed design (c68fdca); v4 mass roll-up retained for the other lines",
           sizing=sizing_basis, flows_mg_s={k: v * 1e6 for k, v in FLOWS.items()},
           feed_design=dict(C_channel_m3_s=C_CH, ring=dict(radial_mm=RING_W * 1e3, axial_mm=RING_H * 1e3, n_inlets=N_IN, cL_m4_s=cL_ring),
                            uniformity_rule=f"+/-{UNIF*100:.0f} % azimuthal flux: outlet dp >= {R_U:.0f} x ring azimuthal dp (assumed H1 requirement)",
                            outlet=dict(n_holes=N_HOLES, d_mm=D_HO * 1e3, t_mm=T_HO * 1e3, C_m3_s=C_OUT, open_fraction_of_channel_base=OPEN_FRAC,
                                        uniformity_ratio_outlet_to_ring=UNIF_RATIO),
                            C_contraction_m3_s=C_CONTR,
                            C_distributor_outlet_m3_s=C_OUT, tree=[dict(count=n, d_mm=d * 1e3, L_mm=Lx * 1e3, T_K=T, C_m3_s=c) for (n, d, Lx, T), c in zip(TREE, C_TREE)],
                            C_manifold_m3_s=C_MAN, C_isolation_valve_m3_s=C_ISO, C_metering_valve_full_m3_s=C_V_FULL,
                            control_authority=AUTH, control_band=BAND),
           feed=feed, plenum_min_controllable_Pa=P_MIN_CTRL, plenum_setpoint_Pa=P_SET, plenum_band_Pa=(P_SET * (1 - BAND), P_SET * (1 + BAND)), plenum_V_L=V_PLEN * 1e3,
           compressor=dict(rpm_both_shafts=RPM, omega_rad_s=OMEGA, S_eff_inlet_m3_s=S_EFF1, p_inlet_Pa=Q(MD_SIZ, T_C) / S_EFF1, rows=ROWS, holweck=HOLW,
                           recheck=recheck_out, kinematics=dict(outer_drum_hoop_stress_MPa=hoop_drum, outer_drum_growth_mm=grow_drum * 1e3,
                                                                holweck_growth_mm=grow_holw * 1e3, holweck_running_clearance_mm=0.3),
                           bom=comp, cbe_kg=round(comp_cbe, 3), mev_kg=round(comp_mev, 3), target_mev_kg=6.5,
                           power_W=dict(rows_shear=P_rows, holweck_shear=P_holw, gas_isothermal=P_gas, bearings=P_bear, shaft=P_shaft, **COMP_P)),
           feed_bom=feed_items, bom_subtotals_mev_kg=sub, v4_subtotals_mev_kg=sub4,
           nonharness_kg=round(nonh, 3), harness_kg=round(harness, 3), nominal_dry_kg=round(nominal, 3), dry_10pct_kg=round(dry, 3),
           wet_2kgXe_kg=round(wet, 3), margin_to_40_kg=round(40 - wet, 3), deficit_kg=round(deficit, 3),
           bus_12mN_W={k: round(v, 1) for k, v in bus12.items()}, next_candidates_if_deficit=rank if deficit > 0 else [])
Path(__file__).with_suffix(".json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(dict(sizing=MD_SIZ * 1e6, p_min=P_MIN_CTRL, p_set=P_SET, feed={k: (round(v["p_anode_Pa"], 3), round(v["p_distributor_Pa"], 3), round(v["p_plenum_required_full_open_Pa"], 3), v["met_at_setpoint"]) for k, v in feed.items()},
                      holes=(N_HOLES, OPEN_FRAC), rows=[(r["row"], r["shaft"], round(r["r_mean_m"], 3), round(r["blade_height_mm"], 1), round(r["u_rel_m_s"]), round(r["p_in_Pa"], 4), round(r["p_out_Pa"], 4), round(r["K"], 2), round(r["Kn_out"], 1)) for r in ROWS],
                      holw={k: (round(v, 3) if isinstance(v, float) else v) for k, v in HOLW.items()}, recheck=recheck_out,
                      comp_cbe=comp_cbe, comp_mev=comp_mev, bom=[(x["item"][:40], x["cbe_kg"]) for x in comp], power=out["compressor"]["power_W"],
                      sub=sub, nominal=nominal, dry=dry, wet=wet, bus12=bus12, kin=out["compressor"]["kinematics"]), indent=1, default=str))
