"""DCR-DBF1-001 final system mass closure v6 (owner instruction 2026-10-10, after v5 at 0757093). Deterministic, < 1 s.
Scope: AL-07 PPU component CBE, AL-08 Xe hardware component rebuild, AL-01 / AL-02 structural integration audit, AL-10 duplication
audit. Compressor architecture, AIR flow, Hall, ICP architecture, 2 kg Xe, harness rule and 10 % system margin unchanged.
Roll-up convention = docs/budgets/mass_power_a9_v5 (A9.26): harness = 0.05/0.95 x non-harness; nominal = non-harness + harness;
dry = 1.10 x nominal; wet = dry + loaded Xe 2 kg. Component MGA by maturity as in the DCR BOMs v3-v5 (measured 5 %, new 20 %).
PROPOSAL-LEVEL / PARAMETRIC / NOT_VALIDATED."""
import json, math
from pathlib import Path
HERE = Path(__file__).parent
v5 = json.loads((HERE / "dcr001_mass_closure_v5.json").read_text())
v3 = json.loads((HERE / "dcr001_gate_closure_v3.json").read_text())
def L(item, cbe, mga, basis, ev): return dict(item=item, cbe_kg=round(cbe, 4), mga=mga, mev_kg=round(cbe * (1 + mga), 4), basis=basis, evidence_class=ev)
def tot(items, k): return round(sum(x[k] for x in items), 4)

# ---------- AL-07 PPU: cathodeless H1 PPU, preliminary component CBE ----------
# Scope (mass_power_a9_v5 partition): discharge supply + per-coil magnet supplies (A9B-25), collector / bias supply (A9B-22, MQ-07).
# NOT in AL-07: valve / flow drivers, housekeeping, control / FDIR and the MIL-1553B + discrete interface (A9B-26 / A9B-27 -> AL-09);
# RF generator, match and RF protection / sensing (AL-06, MPV2-N02); compressor motor drive (AL-02). No C1 heater / keeper supply (A9.20).
# Redundancy (RFP-P18-09 / P18-02, RVM-19 re-based by RVMQ-01): no single-point failure in the electronics -> N+1 discharge modules,
# a spare cross-strapped magnet channel, cold-redundant collector supply, redundant auxiliary supply and PPU control.
P_D_MAX = 887.0                                               # Xe 25 mN discharge allocation at the 1,450 W ceiling (v4)
N_MOD, P_MOD = 3, 500.0                                       # 2 of 3 x 500 W carry 1,000 W >= 887 W (N+1)
assert (N_MOD - 1) * P_MOD >= P_D_MAX
ppu = [
  L("input front end: EMI filter, inrush limiter, 4 latching current limiters (discharge, RF-generator feed, compressor drive, AL-09)", 0.35, 0.2, "estimate", "assumed"),
  L(f"discharge converter: {N_MOD} x {P_MOD:.0f} W phase-shifted full-bridge modules, N+1 (power stage, magnetics, switches, capacitors, PCB)", N_MOD * 0.40, 0.2, "estimate (~0.8 kg/kW power stage; verify)", "assumed"),
  L("discharge output section: OR-ing, output filter, current sensing, ignition / arc protection", 0.25, 0.2, "estimate", "assumed"),
  L("magnet supplies: 3 per-coil channels (inner, outer, trim; ~15 W each) + 1 cross-strapped spare", 4 * 0.08, 0.2, "estimate", "assumed"),
  L("collector / bias supply: floating 100 W class with V/I readback, 2 cold-redundant", 2 * 0.18, 0.2, "estimate", "assumed"),
  L("auxiliary (internal rails) supply, 2 redundant", 2 * 0.08, 0.2, "estimate", "assumed"),
  L("PPU-internal converter control / protection / telemetry boards, 2 redundant (system 1553 / discrete interface is in AL-09)", 2 * 0.12, 0.2, "estimate", "assumed"),
  L("enclosure: Al box ~250 x 200 x 100 mm, 1.5 mm walls + partitions", 0.85, 0.2, "geometry", "model-derived"),
  L("output EMI filters", 0.10, 0.2, "estimate", "assumed"),
  L("connectors (8) + internal wiring", 0.34, 0.2, "estimate", "assumed"),
  L("cold plate / thermal interface: thickened baseplate + interface filler (~50 W dissipation)", 0.28, 0.2, "estimate", "assumed"),
  L("potting, conformal coat, fasteners", 0.10, 0.2, "estimate", "assumed")]
ppu_cbe, ppu_mev = tot(ppu, "cbe_kg"), tot(ppu, "mev_kg")
ppu_crosscheck = dict(
    analog_floor_kg=5.0, analog="SETS PPU 100-500 W (lowest admissible measured analog, mass_power_a9_v5 AL-07)",
    analog_scope_note="the analogs contain functions not in AL-07 now: cathode heater / keeper supplies (no C1 in flight, A9.20) and the "
                      "controller / valve drivers (A9B-26 'inside the PPU analog in H2-7 v1', now booked in AL-09); they are single-string",
    ng_em1_1kW_kg=6.1, governance="the 6.0 kg floor (owner 2026-10-04: do not reduce) is replaced only by a PPU CBE x 1.20 (rebase rule); "
                                  "this preliminary CBE governs only if the owner accepts it as the AL-07 rebase")

# ---------- AL-08 Xe storage / feed hardware, 2 kg loaded Xe ----------
M_XE, MEOP = 2.0, 150e5
V_TANK = 1.25e-3                                              # >= 1.1975 L V_min at 323.15 K, 150 bar incl. EOS uncertainty (xe_ledger_a9_v1)
R_TK = (3 * V_TANK / (4 * math.pi)) ** (1 / 3)
SIG_ULT, BF, RHO_TI = 895e6, 2.0, 4430.0                      # Ti-6Al-4V ultimate (verify), burst factor 2.0 (XA9-29 TBD; conservative)
t_req = BF * MEOP * R_TK / (2 * SIG_ULT); T_TK = max(t_req, 1.2e-3)       # 1.2 mm minimum gauge
shell = 4 * math.pi * R_TK ** 2 * T_TK * RHO_TI
xe = [
  L(f"Ti-6Al-4V spherical shell, {V_TANK*1e3:.2f} L, R {R_TK*1e3:.1f} mm, t {T_TK*1e3:.2f} mm (MEOP 150 bar, burst factor 2)", shell, 0.2, "thin-shell sizing", "model-derived"),
  L("girth-weld land", 0.03, 0.2, "estimate", "assumed"),
  L("2 port bosses (inlet / outlet)", 0.12, 0.2, "estimate", "assumed"),
  L("tank mounting tabs / skirt", 0.08, 0.2, "estimate", "assumed"),
  L("Xe pressure regulator: Moog XFC (A9B-09)", 0.974, 0.05, "measured analog AN-MOOG-XFC", "measured"),
  L("series isolation latch #1 (A9B-10, owner row 55)", 0.170, 0.05, "measured analog AN-MOOG-LATCH-18", "measured"),
  L("series isolation latch #2 (A9B-10, owner row 55; omitted in the DCR v3 BOM)", 0.170, 0.05, "measured analog AN-MOOG-LATCH-18", "measured"),
  L("anode-feed proportional flow control valve (A9B-11; omitted in the DCR v3 BOM)", 0.115, 0.05, "measured analog AN-MOOG-PFCV", "measured"),
  L("pressure transducers: 2 high-pressure (sensor redundancy, RFP-P18-02) + 1 low-pressure", 3 * 0.06, 0.2, "estimate", "assumed"),
  L("filter", 0.03, 0.2, "estimate", "assumed"),
  L("fill / drain service valve (omitted in the DCR v3 BOM)", 0.06, 0.2, "estimate", "assumed"),
  L("plumbing: 1/8 in SS tube ~2.5 m (0.034 kg/m), welded fittings, clamps", 2.5 * 0.0336 + 0.06 + 0.04, 0.2, "geometry + estimate", "model-derived"),
  L("tank strap / bracket to module structure", 0.12, 0.2, "estimate", "assumed"),
  L("tank thermal: 2 redundant heaters + 2 thermostats / RTDs, MLI ~0.06 m2", 0.05 + 0.03, 0.2, "estimate", "assumed")]
xe_cbe, xe_mev = tot(xe, "cbe_kg"), tot(xe, "mev_kg")
xe_double_count = [
  "AL-09: valve / XFC drivers and housekeeping are AL-09 (A9B-26); none are in AL-08 -> no double count",
  "AL-10: Xe tank mounting / thermal are mapped to AL-08 (MQ-07, A9B-08); AL-10 thermal (A9B-30) excludes them -> no double count",
  "PPU: no Xe electronics in AL-07 -> no double count",
  "AL-09 flight sensors (A9B-29, row-62 ICP list) do not include the Xe transducers (A9B-12, AL-08) -> no double count",
  "finding: the DCR v3 AL-08 BOM omitted the second series latch, the PFCV and a fill / drain valve; added here (mass increases)"]

# ---------- AL-01 + AL-02: one mechanical assembly ----------
# Shell: intake shroud (collimator sleeve + collection cone, ~1.05 m2) ends at the rotor face; the compressor housing (rotor cylinder +
# aft closure, ~0.58 m2) starts there -> no overlapping shell area (no shell saving). Interfaces and mounts are the duplicated items.
booked = [dict(line="AL-02", item="housing front flange (share of 'Al flanges / inserts' 0.25)", cbe_kg=0.10),
          dict(line="AL-02", item="housing aft flange to plenum / closure (share)", cbe_kg=0.05),
          dict(line="AL-02", item="bearing / motor carrier inserts (share)", cbe_kg=0.10),
          dict(line="AL-02", item="mounts: brackets to intake shroud / module structure", cbe_kg=0.25),
          dict(line="AL-01", item="collimator support ring (share of 'frame, mounts' 0.50)", cbe_kg=0.20),
          dict(line="AL-01", item="shroud aft interface ring to the compressor (share)", cbe_kg=0.10),
          dict(line="AL-01", item="intake mount feet to module structure (share)", cbe_kg=0.20)]
integrated = [dict(item="collimator support ring (retained)", cbe_kg=0.20),
              dict(item="co-cured shroud-housing overlap joint (CFRP 30 mm x 1 mm band) replacing the bolted flange pair", cbe_kg=2 * math.pi * 0.343 * 0.03 * 0.001 * 1600 + 0.01),
              dict(item="housing aft flange (retained)", cbe_kg=0.05),
              dict(item="bearing / motor carrier inserts (retained)", cbe_kg=0.10),
              dict(item="one set of 4 Ti mount feet at the compressor station for the whole assembly (replaces intake feet + compressor brackets)", cbe_kg=0.25),
              dict(item="local shell reinforcement at the mount station", cbe_kg=0.05)]
int_booked = round(sum(x["cbe_kg"] for x in booked), 4); int_new = round(sum(x["cbe_kg"] for x in integrated), 4)
int_save_cbe = int_booked - int_new; int_save_mev = int_save_cbe * 1.2

# ---------- AL-10 duplication audit ----------
al10 = [
  dict(item="ICP open-frame support / Hall-to-ICP axial spacer", finding="DOUBLE-BOOKED: owner mapping MPQ-02 (MPV2-N04) and A9B-31 put it in AL-10; "
       "the DCR v3 AL-05 BOM also carries 'mount / spacer' 0.20 kg CBE (0.24 MEV)", action="remove the AL-05 duplicate (AL-10 keeps it per MQ-02)", saving_mev=0.24),
  dict(item="intake / compressor mounts vs AL-10 module structure (A9B-31)", finding="AL-10 is an unitemized owner allocation; no specific bracket can be shown to be in both",
       action="none", saving_mev=0.0),
  dict(item="Hall radiator (AL-10) vs anode heat-removal hardware (MPV2-N03 -> AL-04)", finding="the AL-04 floor (H2 head analog) does not contain the radiator; no double booking",
       action="none", saving_mev=0.0),
  dict(item="Xe tank thermal", finding="in AL-08 by MQ-07; excluded from AL-10", action="none", saving_mev=0.0)]
al10_save = sum(x["saving_mev"] for x in al10)

# ---------- roll-up (same convention as mass_power_a9_v5) ----------
sub_old = dict(v5["bom_subtotals_mev_kg"]); sub = dict(sub_old)
sub["AL-07 PPU"] = ppu_mev
sub["AL-08 Xe hardware (single branch, 2 kg Xe)"] = xe_mev
asm_old = sub_old["AL-01 intake"] + sub_old["AL-02 compressor"]
# book the integrated assembly items: collimator ring stays in AL-01; joint, feet, reinforcement, retained housing items in AL-02
sub["AL-01 intake"] = round(sub_old["AL-01 intake"] - (0.10 + 0.20) * 1.2, 4)                      # aft interface ring + intake feet removed
joint = integrated[1]["cbe_kg"]
sub["AL-02 compressor"] = round(sub_old["AL-02 compressor"] - (0.10 + 0.25) * 1.2 + (joint + 0.25 + 0.05) * 1.2, 4)
assert abs((asm_old - sub["AL-01 intake"] - sub["AL-02 compressor"]) - int_save_mev) < 5e-4
sub["AL-05 ICP neutralizer"] = round(sub_old["AL-05 ICP neutralizer"] - al10_save, 4)
def rollup(s):
    nonh = sum(s.values()); harness = 0.05 / 0.95 * nonh; nominal = nonh + harness; dry = 1.10 * nominal; wet = dry + M_XE
    return dict(nonharness_kg=round(nonh, 4), harness_kg=round(harness, 4), nominal_dry_kg=round(nominal, 4), dry_10pct_kg=round(dry, 4),
                wet_2kgXe_kg=round(wet, 4), margin_to_40_kg=round(40 - wet, 4), margin_to_39_4_kg=round(39.4 - wet, 4))
old, new = rollup(sub_old), rollup(sub)
assert abs(old["wet_2kgXe_kg"] - v5["wet_2kgXe_kg"]) < 2e-3, (old, v5["wet_2kgXe_kg"])      # convention reproduces v5 exactly
nonh_max_40 = 38.0 / 1.1 * 0.95; nonh_max_394 = 37.4 / 1.1 * 0.95
convention_check = dict(
    builder="docs/budgets/mass_power_a9_v5/build_mass_power_a9_v5.py (A9.26): harness = 0.05/0.95 x non-harness (row 60 / MQ-06), "
            "nominal = non-harness + harness, dry = 1.10 x nominal, wet = dry + loaded Xe (2 kg planning reference, residual inside)",
    reproduces_v5_rollup=True, v5_wet=v5["wet_2kgXe_kg"], recomputed_v5_wet=old["wet_2kgXe_kg"],
    line_uplift="AL-07 governed as CBE x 1.20 (the floor rebase rule); AL-08 components carry maturity MGA (measured 5 %, new 20 %) as in the "
                "accepted DCR BOMs v3-v5 (the v5 builder's AL-08 is a 1.2 x analog floor of 5.91 kg for a 7 L-class tank, superseded by the DCR "
                "component BOM since v3)",
    nonharness_limit_strict_40_kg=round(nonh_max_40, 4), nonharness_limit_39_4_kg=round(nonh_max_394, 4))
rows = [
  dict(line="AL-07 PPU", current_mev=sub_old["AL-07 PPU"], new_cbe=ppu_cbe, new_mev=ppu_mev, saving=round(sub_old["AL-07 PPU"] - ppu_mev, 4),
       evidence="preliminary component CBE, mostly assumed; enclosure model-derived; governs only on owner acceptance as the AL-07 rebase"),
  dict(line="AL-08 Xe hardware", current_mev=sub_old["AL-08 Xe hardware (single branch, 2 kg Xe)"], new_cbe=xe_cbe, new_mev=xe_mev,
       saving=round(sub_old["AL-08 Xe hardware (single branch, 2 kg Xe)"] - xe_mev, 4),
       evidence="tank model-derived; XFC / latches / PFCV measured analogs; omitted latch #2, PFCV and fill / drain valve added"),
  dict(line="AL-01 + AL-02 integration", current_mev=round(asm_old, 4), new_cbe=None, new_mev=round(sub["AL-01 intake"] + sub["AL-02 compressor"], 4),
       saving=round(int_save_mev, 4), evidence="one assembly: bolted flange pair -> co-cured joint; two mount sets -> one; shell area unchanged; itemization assumed"),
  dict(line="AL-10 audit (duplicate removed from AL-05)", current_mev=sub_old["AL-05 ICP neutralizer"], new_cbe=None, new_mev=sub["AL-05 ICP neutralizer"],
       saving=al10_save, evidence="ICP mount / spacer booked in AL-05 and (MQ-02) AL-10; AL-10 value unchanged at 2.5 kg"),
  dict(line="AL-10 structure / thermal", current_mev=2.5, new_cbe=None, new_mev=2.5, saving=0.0, evidence="owner allocation; no other duplicated hardware identified")]
total_saving = round(sum(r["saving"] for r in rows), 4)
out = dict(label="PROPOSAL-LEVEL / PARAMETRIC / NOT_VALIDATED", supersedes="v5 (0757093) roll-up for AL-01 / 02 / 05 / 07 / 08 only",
           ppu=dict(bom=ppu, cbe_kg=ppu_cbe, mev_kg=ppu_mev, crosscheck=ppu_crosscheck, discharge_rating_W=(N_MOD - 1) * P_MOD),
           xe=dict(bom=xe, cbe_kg=xe_cbe, mev_kg=xe_mev, tank=dict(V_L=V_TANK * 1e3, R_mm=R_TK * 1e3, t_required_mm=t_req * 1e3, t_mm=T_TK * 1e3,
                                                                     MEOP_bar=MEOP / 1e5, burst_factor=BF), double_count_check=xe_double_count),
           integration=dict(booked=booked, integrated=integrated, booked_cbe=int_booked, integrated_cbe=int_new, saving_cbe=round(int_save_cbe, 4),
                            saving_mev=round(int_save_mev, 4), shell_overlap="none (shroud ends at the rotor face; housing starts there)"),
           al10_audit=al10, rows=rows, total_nonharness_saving_kg=total_saving,
           subtotals_old_mev_kg=sub_old, subtotals_new_mev_kg=sub, rollup_old=old, rollup_new=new, convention_check=convention_check,
           required_saving_strict_40_kg=round(sum(sub_old.values()) - nonh_max_40, 4), required_saving_39_4_kg=round(sum(sub_old.values()) - nonh_max_394, 4))
(HERE / "dcr001_system_mass_closure_v6.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(dict(rows=rows, total=total_saving, old=old, new=new, ppu=(ppu_cbe, ppu_mev), xe=(xe_cbe, xe_mev, R_TK, t_req, T_TK, shell),
                      integ=(int_booked, int_new, int_save_mev), req=(out["required_saving_strict_40_kg"], out["required_saving_39_4_kg"]), sub=sub), indent=1))
