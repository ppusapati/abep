# DBF-1.2 freeze gates — status v3 (A9.40)

Generated from `dcr001_gate_closure_v3.py` / `dcr001_gate_closure_v3.json` (sha `098c2e661d27…`) and `dcr001_preliminary_design_v2.json`.
PROPOSAL-LEVEL PRELIMINARY DESIGN · component CBEs from geometry or traceable analogs · NOT measured.

| Gate | Result | State |
|---|---|---|
| Mass | nominal dry 33.76 kg → 37.13 kg with 10 % → **39.13 kg wet** (2 kg Xe); 0.87 kg below 40 kg | CLOSED (≤ 39.4 kg preferred target met) |
| Power | AIR 12 mN 1142 W (reference) / 1189 W (conservative); Xe 25 mN, compressor off: 1182 W (1311 W with +100 W RF) | CLOSED (all < 1,450 W) |
| Operating concept | A9.40 requirement interpretation: density-aware AIR altitude scheduling in 180–230 km; Xe contingency outside the AIR window; the 196 states are a conservative verification set | CLOSED (decision recorded) |
| Host interface | IR-HOST-DRAG-01: host C_D·A provided at PDR within the drag-compensation envelope; reference sizing 0.50 m² | CLOSED (interface requirement) |

Design change inside DCR-001 (v3): the finishing turbo-drag pump is deleted. The front compressor is a 7-stage tapered,
contra-rotating molecular stack (Ø0.66 m first stage, net angular momentum cancelled) delivering to a
9.3 L plenum at 5 Pa (overall pressure ratio ≈1209). Air is metered by a low-pressure variable-conductance valve.
Retaining the finishing pump would give 41.9 kg wet.

Reference altitude schedule at host C_D·A 0.50 m² (all-state, reference Hall basis): LT-low [181.5, 183.0],
LT-moderate [192.0, 196.0], LT-high [210.0, 212.0] km.
ST-high has no all-state AIR altitude at 0.50 m² (maximum 0.48 m² at 221.5 km), so all-state ST-high extremes use Xe contingency per A9.40;
the nominal ST-high window is [206.0, 230.0] km.

Controlled risks carried into DBF-1.2: air-Hall performance basis (26.8 km/s design, 22 km/s sensitivity: T/D_intake 1.14, host allowance 0.20 m²);
full-aperture molecular compressor maturity (new development, CBE 4.96 kg); PPU and RF-generator heat
rejection on host radiating panels via SCI-A (interface requirement); the PPU 6.0 kg and Hall-head 4.2 kg owner floors are unchanged.
