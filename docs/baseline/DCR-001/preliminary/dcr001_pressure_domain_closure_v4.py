"""DCR-DBF1-001 compressor / feed pressure-domain closure v4 (owner instruction 2026-10-10). Deterministic, < 1 s.
1) H1 feed pressure from series molecular / transitional conductances (plenum -> metering valve -> line -> distributor -> channel).
2) Compressor re-sized by pressure domain: turbo blade rows only inside the repository's 0.1 Pa molecular-regime limit (EV-03,
   compressor_downselect_v1); above it a compact turbo-drag finishing unit (turbo rows NOT admitted in the transitional range ->
   analog-class evidence; Holweck / drag channels checked against the repository drag-channel Kn >= 0.5 bound).
3) Component BOM regenerated from v3 with the compressor / plenum lines replaced. 4) Xe 25 mN discharge-power allocation.
PROPOSAL-LEVEL / PARAMETRIC / NOT_VALIDATED."""
import json, math
from pathlib import Path
k_B, amu = 1.380649e-23, 1.66053906660e-27
M = 24 * amu
def Q(mdot, T): return mdot * k_B * T / M                    # Pa m3 / s
def q4(T): return math.sqrt(8 * k_B * T / (math.pi * M)) / 4
LAMBDA_P = 6.8e-3                                             # mean free path x pressure, air ~300 K (Pa m)
# ---------- 1. feed pressure ----------
A_CH = math.pi * 0.070 * 0.012; W_CH = 0.30; T_CH = 500.0       # H1 RP-1 annulus; slot transmission L/h 8.6 (parallel-plate approx.); anode-region gas T (assumed)
C_CH = A_CH * q4(T_CH) * W_CH
R_DIST = 3.0                                                  # distributor uniformity rule p_dist >= 3 p_anode (H1 interface requirement, assumed)
D_LINE, L_LINE = 0.040, 0.20                                  # short large-bore plenum->distributor manifold (a 10 mm x 0.5 m line gives C ~2.7e-4 m3/s: rejected)
C_LINE = math.pi / 12 * D_LINE ** 3 / L_LINE * 4 * q4(300)    # long-tube molecular conductance; Kn(40 mm, 2-6 Pa) ~0.03-0.09 -> transitional, molecular C is a lower bound (conservative dp)
flows = {"AIR_12mN_ref_0.45": 0.45e-6, "AIR_12mN_cons_0.55": 0.55e-6, "AIR_capability_1.33": 1.33e-6}
feed = {}
for k, md in flows.items():
    p_an = Q(md, T_CH) / C_CH; p_d = R_DIST * p_an
    C_dist = Q(md, 300) / (p_d - p_an); dp_line = Q(md, 300) / C_LINE
    feed[k] = dict(p_anode_Pa=p_an, p_distributor_Pa=p_d, C_distributor_req_m3_s=C_dist, dp_line_Pa=dp_line)
# metering valve: Delta p = p_dist at the 12 mN conservative point (50 % opening); full open = 2x that conductance
Cv_nom = Q(0.55e-6, 300) / feed["AIR_12mN_cons_0.55"]["p_distributor_Pa"]; Cv_full = 2 * Cv_nom
for k, md in flows.items():
    f = feed[k]; Cv = Cv_nom if "12mN" in k else Cv_full
    f["dp_valve_Pa"] = Q(md, 300) / Cv; f["p_plenum_min_Pa"] = f["p_distributor_Pa"] + f["dp_line_Pa"] + f["dp_valve_Pa"]
P_PLEN = 12.0; PLEN_BAND = (11.1, 14.0)                     # lower edge = capability-point (1.33 mg/s) requirement 11.09 Pa
plen_min = max(f["p_plenum_min_Pa"] for f in feed.values())
assert P_PLEN >= plen_min, (P_PLEN, plen_min)
# ---------- 2. compressor by pressure domain ----------
A_FACE, W_REV, H1S = 0.70, 1 / (1 + 0.75 * 20), 0.30
S_IN = 2.0 * A_FACE * q4(300) * W_REV
md = 0.55e-6; p_in = Q(md, 300) / S_IN
P_FM_MAX = 0.1                                                # turbo blade-row molecular-regime limit (EV-03)
PR_ST = 2.8; n_front = math.ceil(math.log(P_FM_MAX / p_in) / math.log(PR_ST))
A1 = S_IN / (H1S * q4(300)); A_sum = A1 * (1 - (1 / PR_ST) ** n_front) / (1 - 1 / PR_ST)
stages = []; p = p_in
for i in range(n_front):
    po = min(p * PR_ST, P_FM_MAX); s_sp = 0.020 * (1 / PR_ST) ** (i / 2)    # blade spacing shrinks with stage area
    stages.append(dict(stage=f"F{i+1} front axial (shaft 1, contra-rotating)", p_in_Pa=p, p_out_Pa=po, PR=po / p, Kn_out=LAMBDA_P / (po * s_sp),
                       domain="free molecular (<= 0.1 Pa)", evidence="turbomolecular stage theory inside the admitted 0.1 Pa limit (EV-01..03); stage coefficients not measured"))
    p = po
S_fin = Q(md, 300) / P_FM_MAX
stages.append(dict(stage="T turbo section of finishing unit (shaft 2, ~1 kHz)", p_in_Pa=P_FM_MAX, p_out_Pa=1.0, PR=10.0, Kn_out=LAMBDA_P / (1.0 * 0.004),
                   domain="transitional (blade spacing ~4 mm: Kn 1.7-17)", evidence="NOT admitted in the repository model; analog evidence: commercial turbo-drag hybrid pumps operate turbo rows in this range (EV-03 pump class; verify)"))
G_HOLW = 3e-4
stages.append(dict(stage="H Holweck drag section of finishing unit", p_in_Pa=1.0, p_out_Pa=P_PLEN, PR=P_PLEN, Kn_out=LAMBDA_P / (P_PLEN * G_HOLW),
                   domain=f"molecular-drag channel, gap 0.3 mm: Kn {LAMBDA_P/(P_PLEN*G_HOLW):.1f}-{LAMBDA_P/(1.0*G_HOLW):.0f} (repository drag-channel bound Kn >= 0.5 met)",
                   evidence="drag-channel form ln K0 ~ u sqrt(m) L / h (EV-02, model-derived); coefficients uncited"))
# drag-only finishing check (why a turbo section is needed): S_holweck ~ 0.5 u b h
u_h = 150.0; b_needed = S_fin / (0.5 * u_h * G_HOLW)
def L(item, cbe, mga, basis, ev): return dict(item=item, cbe_kg=round(cbe, 3), mga=mga, mev_kg=round(cbe * (1 + mga), 3), basis=basis, evidence_class=ev)
comp = [
  L(f"front: {n_front}-stage tapered contra-rotating rotor stack (annulus sum {A_sum:.3f} m2 x 2 rows x 1.74 kg/m2)", A_sum * 1.74 * 2, 0.20, "geometry", "model-derived"),
  L("front: 2 shafts, hybrid ceramic bearings, dampers", 1.00, 0.20, "estimate", "assumed"),
  L("front: 2 BLDC motors", 0.80, 0.20, "estimate", "assumed"),
  L("front: conical CFRP housing + flanges", 1.18, 0.20, "geometry", "model-derived"),
  L("front: motor drives (2)", 0.40, 0.20, "estimate", "assumed"),
  L(f"finishing unit rotor: turbo rows (~{S_fin*1e3:.0f} L/s class at 0.1 Pa, Al alloy) + Holweck drum", 1.30, 0.20, "estimate (DN160-class rotor; EV-04 Al-alloy blade sets, ~1 kHz)", "assumed"),
  L("finishing unit: shaft, hybrid / magnetic bearings", 0.50, 0.20, "estimate", "assumed"),
  L("finishing unit: motor", 0.40, 0.20, "estimate", "assumed"),
  L("finishing unit: Al housing integrated with the front housing (no flanges)", 1.00, 0.20, "estimate", "assumed"),
  L("finishing unit: drive electronics", 0.60, 0.20, "estimate", "assumed")]
comp_mev = sum(x["mev_kg"] for x in comp); comp_cbe = sum(x["cbe_kg"] for x in comp)
V_PLEN = 1.0 * Q(0.55e-6, 300) / P_PLEN
# ---------- 3. BOM (v3 lines, compressor + plenum vessel replaced) ----------
v3 = json.loads(Path(__file__).with_name("dcr001_gate_closure_v3.json").read_text())
sub = dict(v3["subtotals_mev_kg"]); sub["AL-02 compressor"] = round(comp_mev, 3)
sub["AL-03 plenum/feed"] = round(sub["AL-03 plenum/feed"] - 0.45 * 1.2 + 0.35 * 1.2, 3)     # plenum vessel 9.3 L -> ~4.7 L
nonh = sum(sub.values()); nominal = nonh / 0.95; harness = nominal - nonh; dry = nominal * 1.1; wet = dry + 2.0
# ---------- 4. power ----------
CH = 0.90 * 0.95
COMP_P = {"target": 45.0, "allowance": 90.0}                  # front stack + finishing unit (bearings, motors, drives); estimate
ND_air = {k: 428.0 + (v - 9.76) / 0.85 for k, v in COMP_P.items()}
bus12 = {"reference": 12e-3 * 26.8e3 / (2 * 0.27) / CH + ND_air["target"], "conservative": 12e-3 * 22e3 / (2 * 0.22) / CH + ND_air["allowance"]}
ND_xe = 424.0 - 9.76 / 0.85
xe = {f"{lim}W_{lab}": round((lim - nd) * CH, 1) for lim in (1500, 1450) for lab, nd in (("nominal_ICP", ND_xe), ("RF_plus_100W", ND_xe + 129.0))}
out = dict(label="PROPOSAL-LEVEL / PARAMETRIC / NOT_VALIDATED", feed=feed, C_channel_m3_s=C_CH, C_line_m3_s=C_LINE, valve_C_nom_m3_s=Cv_nom, valve_C_full_m3_s=Cv_full,
           plenum_min_Pa=plen_min, plenum_selected_Pa=P_PLEN, plenum_band_Pa=PLEN_BAND, plenum_Kn=LAMBDA_P / (P_PLEN * 0.2), plenum_V_L=V_PLEN * 1e3,
           compressor=dict(S_inlet_m3_s=S_IN, p_inlet_Pa_12mN=p_in, n_front=n_front, finishing_inlet_speed_m3_s=S_fin, holweck_only_channel_width_needed_m=b_needed,
                           stages=stages, bom=comp, cbe_kg=round(comp_cbe, 3), mev_kg=round(comp_mev, 3), power_W=COMP_P),
           bom_subtotals_mev_kg=sub, nonharness_kg=round(nonh, 3), harness_kg=round(harness, 3), nominal_dry_kg=round(nominal, 3), dry_10pct_kg=round(dry, 3),
           wet_2kgXe_kg=round(wet, 3), miss_vs_40_kg=round(wet - 40, 3), bus_12mN_W={k: round(v, 1) for k, v in bus12.items()}, xe_25mN_Pd_allocation_W=xe)
Path(__file__).with_name("dcr001_pressure_domain_closure_v4.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: out[k] for k in ("feed", "C_channel_m3_s", "valve_C_nom_m3_s", "plenum_min_Pa", "plenum_V_L", "bom_subtotals_mev_kg", "nonharness_kg", "harness_kg", "nominal_dry_kg", "dry_10pct_kg", "wet_2kgXe_kg", "miss_vs_40_kg", "bus_12mN_W", "xe_25mN_Pd_allocation_W")}, indent=1))
c = out["compressor"]; print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items() if k not in ("stages", "bom")})
for s in c["stages"]: print(s["stage"][:40], f"{s['p_in_Pa']:.4g}->{s['p_out_Pa']:.4g} PR {s['PR']:.2f} Kn {s['Kn_out']:.2f} | {s['domain'][:60]}")
