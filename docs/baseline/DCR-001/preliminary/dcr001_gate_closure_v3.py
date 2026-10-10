"""DCR-DBF1-001 / DBF-1.2 freeze gates (A9.40): component-level preliminary mass BOM and power reroll. Deterministic, < 1 s.
Design change vs v2 (within DCR-001): the separate finishing turbo-drag pump is deleted; the front molecular compressor is a
7-stage tapered contra-rotating stack delivering directly to a 5 Pa plenum; air metering by a low-pressure variable-conductance
valve (the registered Xe valves are specified for 2.8-186 bar inlet, H2-7 R05). MGA by maturity: 5 % measured off-the-shelf
analog, 10 % modified analog, 20 % new design; A9.26 floors keep their x1.2 line uplift; owner MEV allocations unchanged.
PROPOSAL-LEVEL / PARAMETRIC / NOT_VALIDATED; component values are CBEs from geometry or traceable analogs, not measured hardware."""
import json, math
from pathlib import Path
k_B, amu = 1.380649e-23, 1.66053906660e-27
kTm = k_B * 300 / (24 * amu)
A_FACE, LD, W_REV = 0.70, 20.0, 1 / (1 + 0.75 * 20.0)
q4 = math.sqrt(8 * k_B * 300 / (math.pi * 24 * amu)) / 4
S_IN = 2.0 * A_FACE * q4 * W_REV; A1 = S_IN / (0.30 * q4)          # first-stage annulus (H = 0.30)
PR_STAGE, P_PLEN = 2.8, 5.0
mdot12 = 12e-3 / 26.8e3; p_ch12 = mdot12 * kTm / S_IN
N_ST = math.ceil(math.log(P_PLEN / p_ch12) / math.log(PR_STAGE))
A_sum = A1 * (1 - (1 / PR_STAGE) ** N_ST) / (1 - 1 / PR_STAGE)   # tapered stack: stage area ~ volumetric flow
V_PLEN = 1.0 * mdot12 * kTm / P_PLEN                              # 1 s buffer at 12 mN

def L(item, cbe, mga, basis, ev): return dict(item=item, cbe_kg=round(cbe, 3), mga=mga, mev_kg=round(cbe * (1 + mga), 3), basis=basis, evidence_class=ev)
bom = {
 "AL-01 intake": [
   L("Al 5052 honeycomb collimator 1/8 in cell, 32 kg/m3, 0.70 m2 x 64 mm", 0.70 * 0.064 * 32, 0.20, "geometry x catalogue density (verify)", "model-derived"),
   L("collection chamber / shroud, CFRP 0.8 mm, ~1.05 m2", 1.05 * 1.28, 0.20, "geometry x CFRP areal density", "model-derived"),
   L("F4 filter mesh", 0.40 * 0.70, 0.20, "areal estimate", "assumed"),
   L("frame, mounts", 0.50, 0.20, "estimate", "assumed"),
   L("single-shot launch / contamination cover incl. release", 0.30, 0.20, "estimate", "assumed")],
 "AL-02 compressor": [
   L(f"{N_ST}-stage tapered contra-rotating molecular rotor stack (annulus sum {A_sum:.3f} m2 x 2 counter-rotating rows x 1.74 kg/m2)", A_sum * 1.74 * 2, 0.20, "geometry: CFRP 0.5 mm blades, solidity 0.9, Al hub rings", "model-derived"),
   L("2 shafts, hybrid ceramic bearings, dampers", 1.00, 0.20, "estimate (small turbopump bearing analog)", "assumed"),
   L("2 BLDC motors ~30 W continuous", 0.80, 0.20, "estimate (small space motor analog)", "assumed"),
   L("conical CFRP housing + flanges", 0.55 * 1.6 + 0.30, 0.20, "geometry", "model-derived"),
   L("motor drives (2)", 0.40, 0.20, "estimate", "assumed")],
 "AL-03 plenum/feed": [
   L(f"plenum vessel {V_PLEN*1e3:.1f} L (vacuum-rated, thin Al/CFRP)", 0.45, 0.20, "geometry", "model-derived"),
   L("low-pressure variable-conductance metering valves x2 (redundant)", 0.30, 0.20, "estimate (stepper / piezo iris)", "assumed"),
   L("isolation valve", 0.15, 0.20, "estimate", "assumed"),
   L("pressure sensors x2", 0.20, 0.20, "estimate", "assumed"),
   L("lines, fittings", 0.20, 0.20, "estimate", "assumed")],
 "AL-04 Hall head + magnets": [L("H1 Hall head incl. magnetic circuit (A9.26 floor 3.504 kg x 1.2)", 3.504, 0.20, "owner MEV planning floor", "inferred")],
 "AL-05 ICP neutralizer": [
   L("borosilicate tube R0.06 m, L 0.15 m", 0.25, 0.20, "geometry", "model-derived"),
   L("antenna, 3 turns 6 mm Cu tube", 0.15, 0.20, "geometry", "model-derived"),
   L("C-type collector IN600 0.0377 m2 x 1 mm", 0.0377 * 1e-3 * 8470, 0.20, "geometry x density", "model-derived"),
   L("insulators, housing, gas inlet", 0.40, 0.20, "estimate", "assumed"),
   L("mount / spacer", 0.20, 0.20, "estimate", "assumed")],
 "AL-06 RF generator / match": [L("RF generator 13.56 MHz + local match + sensing (owner allocation)", 1.5, 0.0, "owner MEV allocation", "owner-allocation")],
 "AL-07 PPU": [L("Hall PPU incl. bias supplies (A9.26 floor 5.0 kg x 1.2)", 5.0, 0.20, "owner MEV planning floor", "inferred")],
 "AL-08 Xe hardware (single branch, 2 kg Xe)": [
   L("Ti-6Al-4V tank ~1.1 L at <= 150 bar (2 kg Xe, NIST 2045 kg/m3), shell + bosses", 0.80, 0.20, "thin-shell sizing (sigma_allow 440 MPa) + bosses; family analog MT XS-XTA <= 3.5 kg at 1-7 L", "model-derived"),
   L("Moog Xenon Flow Controller (XFC)", 0.974, 0.05, "measured analog (H2-7 AN-MOOG-XFC)", "measured"),
   L("latch / isolation valve", 0.25, 0.10, "analog estimate (verify)", "assumed"),
   L("pressure transducer, filter", 0.15, 0.10, "estimate", "assumed"),
   L("plumbing, fittings", 0.30, 0.20, "estimate", "assumed"),
   L("tank mount, heater, MLI", 0.30, 0.20, "estimate", "assumed")],
 "AL-09 controls / FDIR": [L("controls, valve drivers, flight sensors (owner allocation)", 1.0, 0.0, "owner MEV allocation", "owner-allocation")],
 "AL-10 structure / thermal": [L("module structure, thruster radiator R_HALL 0.15 m2, heat paths (owner allocation)", 2.5, 0.0, "owner MEV allocation; PPU / RF-generator rejection (0.62 + 1.10 m2, P7) via host radiating panels per SCI-A", "owner-allocation")],
}
sub = {k: round(sum(x["mev_kg"] for x in v), 3) for k, v in bom.items()}
nonh = sum(sub.values()); nominal = nonh / 0.95; harness = nominal - nonh
dry = nominal * 1.10; wet = dry + 2.0
# reference: same BOM with the v2 finishing turbo-drag pump + drive retained (20 Pa plenum)
wet_with_finishing = ((nonh + (1.8 + 0.2) * 1.2) / 0.95) * 1.1 + 2.0

# power reroll (P6 ledger basis: non-discharge bus 428 W incl. old compressor 9.76 W; Xe point non-discharge 424 W)
CH = 0.90 * 0.95
def bus(Pd, nd): return Pd / CH + nd
comp = {"target": 25.0, "allowance": 60.0}
ND_air = {k: 428.0 + (v - 9.76) / 0.85 for k, v in comp.items()}
ND_xe = 424.0 - 9.76 / 0.85                                          # atmospheric compressor OFF
power = {
 "AIR_12mN_reference": dict(Pd=12e-3 * 26.8e3 / (2 * 0.27), nd=ND_air["target"]),
 "AIR_12mN_conservative": dict(Pd=12e-3 * 22e3 / (2 * 0.22), nd=ND_air["allowance"]),
 "XE_25mN_parametric_A7": dict(Pd=658.0, nd=ND_xe, basis="RP-1 Xe A7 runs near 25 mN: 23.3-23.8 mN at 442-617 W; 38 mN/kW lowest T/P -> 658 W (PARAMETRIC / NOT_VALIDATED)"),
 "XE_25mN_RF_plus_100W": dict(Pd=658.0, nd=ND_xe + 129.0, basis="sensitivity: +100 W RF forward power (P6: ~1.29 W bus per W RF)"),
}
for v in power.values(): v["bus_W"] = round(bus(v["Pd"], v["nd"]), 1); v["margin_to_1500_W"] = round(1500 - v["bus_W"], 1); v["Pd"] = round(v["Pd"], 1); v["nd"] = round(v["nd"], 1)
out = dict(label="PROPOSAL-LEVEL PRELIMINARY / COMPONENT CBE (not measured)",
           compressor_design=dict(stages=N_ST, PR_stage=PR_STAGE, rotor_D1_m=math.sqrt(A1 / (math.pi / 4 * 0.84)), A1_m2=A1, annulus_sum_m2=A_sum, S_inlet_m3_s=S_IN,
                                  p_inlet_Pa_12mN=p_ch12, p_plenum_Pa=P_PLEN, PR_total=P_PLEN / p_ch12, plenum_V_L=V_PLEN * 1e3, finishing_pump="deleted (plenum 5 Pa)",
                                  angular_momentum="cancelled by contra-rotating rows"),
           bom=bom, subtotals_mev_kg=sub, nonharness_kg=round(nonh, 3), harness_kg=round(harness, 3), nominal_dry_kg=round(nominal, 3),
           dry_10pct_kg=round(dry, 3), wet_2kgXe_kg=round(wet, 3), margin_to_40_kg=round(40 - wet, 3), target_39_4_met=wet <= 39.4,
           wet_if_finishing_pump_retained_kg=round(wet_with_finishing, 3), power=power)
Path(__file__).with_name("dcr001_gate_closure_v3.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: out[k] for k in ("compressor_design", "subtotals_mev_kg", "nonharness_kg", "harness_kg", "nominal_dry_kg", "dry_10pct_kg", "wet_2kgXe_kg", "margin_to_40_kg", "wet_if_finishing_pump_retained_kg", "power")}, indent=1))
