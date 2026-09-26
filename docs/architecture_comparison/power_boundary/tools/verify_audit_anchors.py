"""Check that every file:line anchor cited in BUS_POWER_BOUNDARY.md (discrepancy audit) still shows the quoted code.

The audit was written against commit daa0e759e26416847f200a4781194f266be27c5c. Line numbers drift when the audited
modules change; this script says which anchors no longer match so the audit can be re-read, never silently trusted.
Read-only; standard library only.   Usage: python verify_audit_anchors.py   (exit 0 = all anchors match)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
AUDITED_COMMIT = "daa0e759e26416847f200a4781194f266be27c5c"

# (path, line, substring that must appear on that line)
ANCHORS = [
    ("abep_sim/archengine.py", 113, 'Ionizer("hall_internal", "hall_internal"'),
    ("abep_sim/archengine.py", 116, 'Ionizer("rf_icp", "plasma"'),
    ("abep_sim/archengine.py", 117, 'Ionizer("helicon", "plasma"'),
    ("abep_sim/archengine.py", 118, 'Ionizer("ecr", "plasma"'),
    ("abep_sim/archengine.py", 194, "src = ECRSource(P_dc_W=P_dc)"),
    ("abep_sim/archengine.py", 198, "src = RFSource(P_dc_W=P_dc, p_min_Pa=io.p_min_Pa)"),
    ("abep_sim/archengine.py", 456, 'if ac.family == "nozzle":'),
    ("abep_sim/archengine.py", 458, 'if io.source_kind == "ecr" and x["B0"] < 0.0875:'),
    ("abep_sim/archengine.py", 461, "st, neut = _ion_source(io, flows, p_in, P_ion, exit_area, wall_f)"),
    ("abep_sim/archengine.py", 484, 'P_acc = hr["P_d_W"]'),
    ("abep_sim/archengine.py", 540, '"P_neut_W": cath["P_W"]'),
    ("abep_sim/archengine.py", 557, 'v["P_ion"] = ([0.0, 50.0, 100.0, 200.0, 350.0] if ac.family == "hall" else'),
    ("abep_sim/archengine.py", 582, "from .ppu import default_ppu, load_modes, Converter"),
    ("abep_sim/archengine.py", 614, 'has_s1 = io.output == "plasma" and pr["P_ion_W"] > 0'),
    ("abep_sim/archengine.py", 615, 'V_conv = max(pr["V_main"], 12.0)'),
    ("abep_sim/archengine.py", 616, "ppu = default_ppu(V_conv,"),
    ("abep_sim/archengine.py", 627, 'P_mag = 25.0 if ac.family in ("hall", "nozzle") or io.source_kind == "ecr" else 0.0'),
    ("abep_sim/archengine.py", 628, 'demand = {"magnet": P_mag / 12.0, "motor": gas["comp_power"] / 48.0, "aux": 1.0}'),
    ("abep_sim/archengine.py", 629, 'if ac.family == "hall": demand["anode"] = pr["P_acc_W"] / V_conv'),
    ("abep_sim/archengine.py", 631, 'if ne.name == "lab6_xe": demand["keeper"] = pr["P_neut_W"] / 30.0'),
    ("abep_sim/archengine.py", 635, 'if has_s1: demand["hv_mw" if s1_kind == "ecr" else "rf_amp"] = pr["P_ion_W"] / (4000.0 if s1_kind == "ecr" else 50.0)'),
    ("abep_sim/archengine.py", 636, 'demand["cathode_src"] = pr["P_neut_W"] / 50.0'),
    ("abep_sim/archengine.py", 637, "loads = ppu.loads(demand)"),
    ("abep_sim/archengine.py", 638, 'P_bus = loads["P_bus_W"]'),
    ("abep_sim/archengine.py", 641, 'if P_bus > dc.P_bus_max_W: rej("power"); continue'),
    ("abep_sim/archengine.py", 653, 'from_acc = min(P_jet, pr["P_acc_W"]); from_src = min(P_jet - from_acc, pr["P_ion_W"])'),
    ("abep_sim/archengine.py", 656, '"ionizer": pr["P_ion_W"] - from_src'),
    ("abep_sim/archengine.py", 657, '"magnets": P_mag, "compressor": gas["comp_power"], "aux": 5.0'),
    ("abep_sim/archengine.py", 658, '"ppu_loss_control": loads["P_loss_W"]'),
    ("abep_sim/archengine.py", 659, 'resid = (P_bus - sum(ledger.values())) / P_bus'),
    ("abep_sim/archengine.py", 660, 'if abs(resid) > 0.02: rej("energy_ledger"); continue'),
    ("abep_sim/archengine.py", 665, 'nodes[4].P_int_W = ledger["ionizer"]'),
    ("abep_sim/archengine.py", 673, '"reservoir_feed": 1.1, "ionizer": io.mass_kg'),
    ("abep_sim/archengine.py", 708, '/ max(loads["eta_overall"], 0.5) + 12'),
    ("abep_sim/archengine.py", 815, 'P_dev = pr["P_acc_W"] + pr["P_ion_W"] + pr["P_neut_W"] + d["P_mag"] + d["comp_power"] + 5.0'),
    ("abep_sim/archengine.py", 818, 'P_dev = d["P_mag"] + d["comp_power"] + 5.0 + 45.0'),
    ("abep_sim/archengine.py", 819, 'P.append(P_dev / max(d["eta_ppu"], 0.5) + 12.0)'),
    ("abep_sim/archengine.py", 888, '"comp_power": r["P_comp_W"]'),
    ("abep_sim/ppu.py", 28, "def efficiency(self, I_out: float, T_K: float = 300.0, V_bus: float = 28.0) -> float:"),
    ("abep_sim/ppu.py", 38, "return max(min(eta, 0.985), 0.3)"),
    ("abep_sim/ppu.py", 47, "V_bus: float = 28.0"),
    ("abep_sim/ppu.py", 52, "controller_W: float = 8.0"),
    ("abep_sim/ppu.py", 54, "sensors_W: float = 4.0"),
    ("abep_sim/ppu.py", 61, "P_bus = self.controller_W + self.sensors_W"),
    ("abep_sim/ppu.py", 75, "P_in = P_out / eta"),
    ("abep_sim/ppu.py", 78, '"P_loss_W": loss + self.controller_W + self.sensors_W'),
    ("abep_sim/ppu.py", 79, '"eta_overall": (P_bus - loss - self.controller_W - self.sensors_W) / P_bus'),
    ("abep_sim/ppu.py", 94, 'Converter("anode", Vd,'),
    ("abep_sim/ppu.py", 95, 'Converter("magnet", 12.0,'),
    ("abep_sim/ppu.py", 96, 'Converter("keeper", 30.0,'),
    ("abep_sim/ppu.py", 97, 'Converter("heater", 8.0,'),
    ("abep_sim/ppu.py", 98, 'Converter("motor", 48.0,'),
    ("abep_sim/ppu.py", 99, 'Converter("aux", 5.0,'),
    ("abep_sim/ppu.py", 103, 'Converter("hv_mw", 4000.0,'),
    ("abep_sim/ppu.py", 105, 'Converter("rf_amp", 50.0,'),
    ("abep_sim/ppu.py", 115, 'startup = {"heater": heater_I_start,'),
    ("abep_sim/plasma_devices.py", 24, "eta_dc_mw: float = 0.65"),
    ("abep_sim/plasma_devices.py", 25, "eta_feed: float = 0.90"),
    ("abep_sim/plasma_devices.py", 45, "eta_dc_rf: float = 0.80"),
    ("abep_sim/plasma_devices.py", 53, "eta = self.eta_dc_rf * gate * R_p / (R_p + self.R_coil_ohm)"),
    ("abep_sim/plasma_devices.py", 266, "heater_W: float = 30.0"),
    ("abep_sim/plasma_devices.py", 267, "keeper_W: float = 15.0"),
    ("abep_sim/plasma_devices.py", 298, '"P_W": self.heater_W * (T / 1700.0) ** 4 * 0.6 + self.keeper_W'),
    ("abep_sim/plasma_devices.py", 133, "eta_v_base: float = 0.85"),
    ("abep_sim/plasma_devices.py", 527, 'I_e = st["I_e"]; I_d = I_beam + I_e'),
    ("abep_sim/plasma_devices.py", 551, '"P_d_W": I_d * Vd'),
    ("abep_sim/compressor.py", 137, "P_el = (P_gas + P_bear) / self.eta_motor + self.P_ctrl_W"),
    ("abep_sim/system.py", 15, "ppu_eff: float = 0.90"),
    ("abep_sim/system.py", 16, "p_ctrl_valves_sensors_W: float = 30.0"),
    ("abep_sim/system.py", 193, "bus = (perf[\"P_thruster_W\"] + cmp_[\"comp_power_W\"] + b.p_ctrl_valves_sensors_W) / b.ppu_eff"),
    ("abep_sim/system.py", 278, "modes = load_modes(ppu, I_d, card.p_magnet_W / 12.0, 1.5, P_s1, P_comp)"),
    ("abep_sim/system.py", 285, 'P_bus_steady = modes["steady"]["P_bus_W"] + b.p_ctrl_valves_sensors_W * 0.0'),
    ("abep_sim/mission_env.py", 33, "eps_eff: float = 0.90"),
    ("abep_sim/mission_env.py", 34, "bus_housekeeping_W: float = 120.0"),
    ("abep_sim/mission_env.py", 161, "P_need = P_bus + sc.bus_housekeeping_W"),
]


DOC = Path(__file__).resolve().parents[1] / "BUS_POWER_BOUNDARY.md"
_MODULES = {"archengine", "ppu", "plasma_devices", "compressor", "system", "mission_env"}
_REF = re.compile(r"`(?:(?P<mod>[a-z_]+)\.py)?:(?P<a>\d+)(?:-(?P<b>\d+))?`")


def doc_references() -> set[tuple[str, int]]:
    """Every `module.py:N` / `module.py:N-M` reference in the document, plus bare `:N` continuations, which refer to the
    module most recently named on the same line."""
    refs = set()
    for text_line in DOC.read_text().splitlines():
        current = None
        for m in _REF.finditer(text_line):
            if m["mod"]:
                current = m["mod"]
            if current not in _MODULES:
                continue
            a = int(m["a"]); b = int(m["b"]) if m["b"] else a
            refs.update({(f"abep_sim/{current}.py", a), (f"abep_sim/{current}.py", b)})
    return refs


def main() -> int:
    bad = 0
    cache: dict[str, list[str]] = {}
    for path, line, needle in ANCHORS:
        lines = cache.setdefault(path, (REPO / path).read_text().splitlines())
        ok = 1 <= line <= len(lines) and needle in lines[line - 1]
        bad += not ok
        print(f"{'OK  ' if ok else 'MISS'} {path}:{line}  {needle}")
    registered = {(p, n) for p, n, _ in ANCHORS}
    unchecked = sorted(doc_references() - registered)
    for path, line in unchecked:
        print(f"UNCHECKED {path}:{line} is cited in {DOC.name} but has no anchor here")
    print(f"{len(ANCHORS) - bad}/{len(ANCHORS)} anchors match (audit written at {AUDITED_COMMIT[:12]}); "
          f"{len(doc_references())} distinct document references, {len(unchecked)} without an anchor")
    return 1 if (bad or unchecked) else 0


if __name__ == "__main__":
    sys.exit(main())
