"""DCR-DBF1-001 proposal-level preliminary sizing: variable-effective-capture intake -> compressor -> plenum/feed -> H1.
Deterministic, runs in < 1 s. Registered inputs are read from the repository; every engineering / literature value is a
named ASSUMPTION with a range. Output: dcr001_preliminary_design_v1.json. PARAMETRIC / NOT_VALIDATED / proposal level."""
import json, math, re, statistics as st, hashlib, collections
from pathlib import Path
R = Path(__file__).resolve().parents[4]
A4 = R / "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/conservation_bounds_v1.json"
k_B, amu, e = 1.380649e-23, 1.66053906660e-27, 1.602176634e-19

# ---------------- registered inputs ----------------
a4 = json.loads(A4.read_text())
grid = collections.defaultdict(list); Us = []
for s in a4["states"]:
    m = re.match(r"ds2:([A-Z_]+):alt(\d+):", s["state_id"])
    grid[(m.group(1), int(m.group(2)))].append(s["Phi_adm_kg_m2_s"]); Us.append(0.5 * (s["U_m_s"]["V_orb_max"] + s["U_m_s"]["V_orb_min"]))
COND = ["ECSS_LT_LOW", "ECSS_LT_MODERATE", "ECSS_LT_HIGH", "ECSS_ST_HIGH"]; ALT = [180, 195, 215, 230]
U = st.median(Us)
# intake-face drag coefficient from the registered F1 TPMC drag of the DBF-1 intake: 17.6 mN at 0.25 m2 at the densest state
K_D = 17.6e-3 / (max(max(v) for v in grid.values()) * U * 0.25)
# power ledger (docs/closure/power/power_ledger_v1.json): non-discharge bus ~428 W incl. old compressor 9.76 W; conversion
P_ND_OLD, P_COMP_OLD = 428.0, 9.76
ETA_DISCH_CHAIN = 0.90 * 0.95            # discharge supply x front end (P6)
# mass roll-up (docs/budgets/mass_power_a9_v5): non-harness 33.1196 kg incl. AL-01 3.5, AL-02 5.5, AL-03 1.0; harness 5/95
NONHARNESS_OLD, AL01, AL02, AL03 = 33.1196, 3.5, 5.5, 1.0

# ---------------- assumptions (proposal level; ranges carried) ----------------
A = dict(
  W_fwd=(0.72, 0.68, 0.92, "TPMC transmission into the collection chamber, unfavourable-scenario band (A5 record, all 10 surface scenarios)"),
  eta_filter=(0.90, 0.70, 0.90, "F4 filter transmission (DBF-1 F4-FIL-T0.9)"),
  LD=(20.0, 15.0, 30.0, "honeycomb collimator length / cell diameter"),
  H_stage=(0.30, 0.25, 0.40, "first-stage pumping probability (Ho coefficient), axial molecular stage at blade-speed ratio ~0.66 (turbomolecular stage theory; verify)"),
  S_over_Cback=(2.0, 1.5, 3.0, "compressor inlet speed / intake back-conductance (sizing choice)"),
  eta_deliv=(0.98, 0.95, 0.99, "compressor + plenum delivery (leakage) efficiency"),
  v_eff_12=(26.8e3, 22e3, 30e3, "air-Hall effective exhaust velocity at 350 V: mean ion 22 amu, mass util 0.6, voltage util 0.8, cos 0.9 (literature-planning, NOT H1 performance)"),
  eta_T=(0.27, 0.22, 0.32, "air-Hall total efficiency (literature-planning, NOT H1 performance)"),
  hub_ratio=(0.40, 0.35, 0.50, "axial rotor hub / tip diameter"),
  v_tip=(300.0, 250.0, 350.0, "rotor tip speed m/s (Al-alloy / CFRP blisk)"),
  T_gas=(300.0, 280.0, 330.0, "chamber gas temperature K"),
  m_mix_amu=(24.0, 21.0, 28.9, "captured-gas mean molecular mass (O/N2 mixture)"),
)
a = {k: v[0] for k, v in A.items()}
Wrev = 1.0 / (1.0 + 0.75 * a["LD"])                      # Clausing-type reverse transmission, long tube approx.
vbar = math.sqrt(8 * k_B * a["T_gas"] / (math.pi * a["m_mix_amu"] * amu)); q4 = vbar / 4
eta_ret = a["S_over_Cback"] / (1 + a["S_over_Cback"])
eta_path = a["W_fwd"] * a["eta_filter"] * eta_ret * a["eta_deliv"]
TD = eta_path * a["v_eff_12"] / (K_D * U)                  # thrust / intake-drag ratio in the flow-limited regime

# required delivered flow
vmax = math.sqrt(2 * e * 350 / (16 * amu))                 # O+ at V_d,max: conservation lower bound
flows = {T: {"lower_bound_kg_s": T / vmax, "engineering_kg_s": T / a["v_eff_12"]} for T in (12e-3, 25e-3)}
v25 = 2 * a["eta_T"] / 2.84e-5                               # 25 mN mode at the discharge ceiling (T/P ~28 mN/kW)
flows[25e-3]["engineering_kg_s"] = 25e-3 / v25

# altitude interpolation of orbit-min and orbit-median flux (log-linear between registered altitudes)
def prof(c, f):
    pts = [(h, f(grid[(c, h)])) for h in ALT]
    def at(h):
        for (h0, y0), (h1, y1) in zip(pts, pts[1:]):
            if h0 <= h <= h1: return y0 * (y1 / y0) ** ((h - h0) / (h1 - h0))
    return at
pmin = {c: prof(c, min) for c in COND}; pmed = {c: prof(c, st.median) for c in COND}; pmax = {c: prof(c, max) for c in COND}

def window(A_face, cda_host):
    phi_lo = flows[12e-3]["engineering_kg_s"] / (eta_path * A_face)
    phi_hi = 25e-3 / (U * (K_D * A_face + 0.5 * cda_host))
    sched = {}
    for c in COND:
        ok = [h / 2 for h in range(360, 461) if pmin[c](h / 2) >= phi_lo and pmed[c](h / 2) <= phi_hi]
        sched[c] = [min(ok), max(ok)] if ok else None
    return phi_lo, phi_hi, sched

# select the smallest aperture (0.05 m2 steps) whose window gives every condition a feasible altitude with >= 10 % flux
# margin on the governing low end, then the largest host C_D*A for which the schedule still exists
sel = None
for i in range(8, 41):
    Af = i * 0.05
    lo, hi, sc = window(Af, 0.0)
    if all(sc.values()) and pmin["ECSS_LT_LOW"](180) >= 1.10 * lo: sel = Af; break
A_face = sel
cda_flow = 2 * (TD - 1) * K_D * A_face          # host C_D*A that the flow-limited thrust margin can carry (T >= D_intake + D_host)
cda = 0.0
while cda + 0.01 <= cda_flow and all(window(A_face, cda + 0.01)[2].values()): cda += 0.01
CDA_REF = 0.5                                      # reference host C_D*A for the published schedule (ICD-dependent)
phi_lo, phi_hi, sched = window(A_face, CDA_REF)
_, phi_hi0, sched0 = window(A_face, 0.0)
phi_hi_intake_only = 25e-3 / (U * K_D * A_face)

# compressor sizing
C_back = A_face * q4 * Wrev; S1 = a["S_over_Cback"] * C_back
A_rot = S1 / (a["H_stage"] * q4); D_rot = math.sqrt(A_rot / (math.pi / 4 * (1 - a["hub_ratio"] ** 2)))
rpm = a["v_tip"] / (math.pi * D_rot) * 60
kTm = k_B * a["T_gas"] / (a["m_mix_amu"] * amu)
mdot25 = flows[25e-3]["engineering_kg_s"]; mdot12 = flows[12e-3]["engineering_kg_s"]
p_ch12, p_ch25 = mdot12 * kTm / S1, mdot25 * kTm / S1
p_inter, p_plen, p_band = 2.0, 20.0, (10.0, 30.0)          # Pa: front-section exit, plenum setpoint and band
S2_needed = mdot25 * kTm / p_inter
PR_front, PR_total = p_inter / p_ch12, p_plen / p_ch12
P_isoth = mdot25 * kTm * math.log(p_plen / p_ch25)          # isothermal compression work (W)
comp_P_nom, comp_P_worst = 25.0, 40.0                       # bearings + motors + drives (ASSUMPTION, analog-based)
# plenum
tau = 2.0; V_plen = tau * mdot12 * kTm / p_plen

# masses (engineering estimates)
L_hc = a["LD"] * 3.2e-3
m_intake = dict(honeycomb=A_face * L_hc * 32.0, chamber_shroud_CFRP=1.2 * 1.5 * A_face, filter=0.4 * A_face, frame_mounts=0.5, launch_cover=0.3)
m_comp = dict(front_axial_rotors_6=6 * 0.30, front_stators_6=6 * 0.20, shaft_hub_bearings=0.6, front_motor=0.5, housing=0.9, finishing_turbodrag=1.6, motor_drives_2=0.8)
m_plen = dict(plenum_vessel_5L=0.5, PFCV_valves_2=0.3, pressure_transducers_2=0.1, lines_fittings=0.2)
mi, mc, mp = sum(m_intake.values()), sum(m_comp.values()), sum(m_plen.values())
nonharness = NONHARNESS_OLD - AL01 - AL02 - AL03 + mi + mc + mp
harness = nonharness * 5 / 95; dry = nonharness + harness; dry_m = dry * 1.10; wet = dry_m + 2.0

# power
dP_bus_nom = (comp_P_nom - P_COMP_OLD) / 0.85; dP_bus_worst = (comp_P_worst - 11.13) / 0.85
ND = P_ND_OLD + dP_bus_nom; ND_w = P_ND_OLD + dP_bus_worst
Pd12 = 12e-3 * a["v_eff_12"] / (2 * a["eta_T"])
Pd_ceiling_1500 = (1500 - ND_w) * ETA_DISCH_CHAIN; Pd_ceiling_1350 = (1350 - ND) * ETA_DISCH_CHAIN
bus12 = Pd12 / ETA_DISCH_CHAIN + ND
Pd25 = 25e-3 * v25 / (2 * a["eta_T"]); bus25 = Pd25 / ETA_DISCH_CHAIN + ND_w

out = dict(
  label="PROPOSAL-LEVEL PRELIMINARY DESIGN / PARAMETRIC / NOT_VALIDATED", inputs=dict(A4_sha256=hashlib.sha256(A4.read_bytes()).hexdigest(), U_m_s=U, K_D_intake=K_D),
  assumptions={k: dict(value=v[0], low=v[1], high=v[2], basis=v[3]) for k, v in A.items()},
  intake=dict(A_face_m2=A_face, D_equiv_m=math.sqrt(4 * A_face / math.pi), LD=a["LD"], cell_mm=3.2, depth_mm=L_hc * 1e3, W_rev=Wrev, eta_retention=eta_ret, eta_path=eta_path,
              effective_capture_m2_max=eta_path * A_face, mass_kg=m_intake, mass_total_kg=mi,
              drag_N_at=dict(phi_lo=K_D * phi_lo * U * A_face, phi_hi=K_D * phi_hi * U * A_face, densest_registered=K_D * max(max(v) for v in grid.values()) * U * A_face)),
  thrust_over_intake_drag=TD,
  flows=flows, v_eff_25_mode_m_s=v25,
  window=dict(phi_lo=phi_lo, phi_hi_with_ref_host=phi_hi, host_CDA_ref_m2=CDA_REF, schedule_km_intake_only=sched0, phi_hi_no_host=phi_hi0, host_CDA_max_flow_margin_m2=cda_flow, phi_hi_intake_only=phi_hi_intake_only, host_CDA_max_m2=cda, ratio=phi_hi / phi_lo,
              rho_lo=phi_lo / U, rho_hi=phi_hi / U, schedule_km=sched,
              flux_margin_LT_LOW_180=pmin["ECSS_LT_LOW"](180) / phi_lo - 1),
  compressor=dict(C_back_m3_s=C_back, S_inlet_m3_s=S1, rotor_annulus_m2=A_rot, rotor_D_m=D_rot, hub_ratio=a["hub_ratio"], rpm_front=rpm, v_tip=a["v_tip"],
                  p_chamber_Pa_12=p_ch12, p_chamber_Pa_25=p_ch25, p_front_exit_Pa=p_inter, finishing_speed_needed_m3_s=S2_needed,
                  PR_front=PR_front, PR_front_per_stage_6=PR_front ** (1 / 6), phi_for_25mN_air=mdot25 / (eta_path * A_face), PR_total=PR_total, P_isothermal_W_25=P_isoth, P_nom_W=comp_P_nom, P_worst_W=comp_P_worst,
                  mass_kg=m_comp, mass_total_kg=mc, turndown_speed=">= 3:1 (30-100 % speed)"),
  plenum=dict(V_m3=V_plen, p_set_Pa=p_plen, p_band_Pa=p_band, tau_s=tau, mass_kg=m_plen, mass_total_kg=mp, power_W=5.0),
  power=dict(nondischarge_bus_nom_W=ND, nondischarge_bus_worst_W=ND_w, Pd_12_W=Pd12, bus_12_W=bus12, Pd_25_W=Pd25, bus_25_W=bus25,
             Pd_ceiling_1500_W=Pd_ceiling_1500, Pd_ceiling_1350_W=Pd_ceiling_1350),
  mass=dict(nonharness_kg=nonharness, harness_kg=harness, nominal_dry_kg=dry, dry_with_10pct_kg=dry_m, wet_2kgXe_kg=wet,
            over_34_nominal_kg=dry - 34.0, over_40_wet_kg=wet - 40.0),
)
Path(__file__).with_name("dcr001_preliminary_design_v1.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: out[k] for k in ("intake", "thrust_over_intake_drag", "window", "compressor", "plenum", "power", "mass")}, indent=1, default=str)[:6000])
