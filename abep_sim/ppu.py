"""Power processing and electrical loads (Phase 4, items 27, 28, 29).

Each converter has an efficiency map eta(V_in, V_out, I_out, T) built from a switching-loss model:
  eta = 1 - (P_fixed + k_cond * I^2 + k_sw * V_out * I * f_sw_norm) / P_out   (bounded)
Mass from topology class (kg/kW + magnetics + housing), doubled for cold-redundant units, plus harness,
sensors, controller and a switching/isolation network. Modes: startup (heater + compressor spin-up + keeper),
steady, peak (Xe augmentation / solar max). Redundancy per RFP: no single-point failure in electronics.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass
class Converter:
    name: str
    V_out: float
    I_max: float
    kind: str                      # "anode" | "magnet" | "keeper" | "heater" | "hv_mw" | "motor" | "aux"
    P_fixed_W: float = 3.0
    k_cond: float = 0.35           # W/A^2
    k_sw: float = 0.012            # switching loss fraction of V*I at nominal f_sw
    kg_per_kW: float = 1.8
    m_base_kg: float = 0.25
    redundant: bool = True         # cold-redundant duplicate
    T_derate_per_K: float = 0.0004 # efficiency loss per K above 300 K

    def efficiency(self, I_out: float, T_K: float = 300.0, V_bus: float = 28.0) -> float:
        if I_out <= 0:
            return 0.0
        P_out = self.V_out * I_out
        # topology penalty for large step-up (anode 300 V from 28 V bus) or step-down
        ratio = max(self.V_out / V_bus, V_bus / self.V_out)
        k_sw = self.k_sw * (1 + 0.04 * math.log(ratio))
        loss = self.P_fixed_W + self.k_cond * I_out ** 2 + k_sw * P_out
        eta = P_out / (P_out + loss)
        eta -= self.T_derate_per_K * max(T_K - 300.0, 0.0)
        return max(min(eta, 0.985), 0.3)

    def mass(self) -> float:
        m = self.m_base_kg + self.kg_per_kW * (self.V_out * self.I_max / 1000.0)
        return m * (2.0 if self.redundant else 1.0)


@dataclass
class PPU:
    V_bus: float = 28.0
    converters: list = field(default_factory=list)
    harness_kg_per_kW: float = 0.9
    harness_base_kg: float = 0.6
    controller_kg: float = 0.7        # rad-tolerant MCU/FPGA + 1553B, redundant
    controller_W: float = 8.0
    sensors_kg: float = 0.4
    sensors_W: float = 4.0
    switch_matrix_kg: float = 0.5
    housing_frac: float = 0.25        # enclosure/shielding as fraction of electronics mass
    shield_al_mm: float = 2.0         # radiation shielding wall thickness (Phase 5 uses it)

    def loads(self, demand: dict, T_K: float = 300.0) -> dict:
        """demand: {converter_name: I_out_A}. Returns bus power, losses, per-converter efficiency."""
        P_bus = self.controller_W + self.sensors_W
        loss = 0.0; detail = {}; violations = []
        for name in demand:
            if name not in {c.name for c in self.converters} and demand[name] > 0:
                violations.append(f"{name}: no converter")
        for c in self.converters:
            I = demand.get(c.name, 0.0)
            if I <= 0:
                detail[c.name] = {"P_out": 0.0, "eta": 0.0, "P_in": 0.0}
                continue
            if I > c.I_max:
                violations.append(f"{c.name}: {I:.2f} A > {c.I_max:.2f} A rated")
            eta = c.efficiency(I, T_K, self.V_bus)
            P_out = c.V_out * I
            P_in = P_out / eta
            P_bus += P_in; loss += P_in - P_out
            detail[c.name] = {"P_out": P_out, "eta": eta, "P_in": P_in}
        return {"P_bus_W": P_bus, "P_loss_W": loss + self.controller_W + self.sensors_W, "detail": detail,
                "eta_overall": (P_bus - loss - self.controller_W - self.sensors_W) / P_bus if P_bus > 0 else 0.0,
                "rating_ok": not violations, "violations": violations}

    def mass(self, P_peak_W: float) -> dict:
        m_conv = sum(c.mass() for c in self.converters)
        m_harn = self.harness_base_kg + self.harness_kg_per_kW * P_peak_W / 1000.0
        m_el = m_conv + self.controller_kg + self.sensors_kg + self.switch_matrix_kg
        m_house = self.housing_frac * m_el
        return {"m_converters_kg": m_conv, "m_harness_kg": m_harn, "m_controller_kg": self.controller_kg,
                "m_sensors_kg": self.sensors_kg, "m_switch_kg": self.switch_matrix_kg, "m_housing_kg": m_house,
                "m_ppu_total_kg": m_el + m_house + m_harn}


def default_ppu(Vd: float, I_d_max: float, has_stage1: bool, stage1_kind: str, P_s1_max_W: float, P_comp_max_W: float) -> PPU:
    conv = [
        Converter("anode", Vd, I_d_max * 1.3, "anode", P_fixed_W=4, k_cond=0.3, k_sw=0.014, kg_per_kW=1.6),
        Converter("magnet", 12.0, 4.0, "magnet", P_fixed_W=1.5, k_cond=0.15, k_sw=0.01, kg_per_kW=2.5, m_base_kg=0.15),
        Converter("keeper", 30.0, 2.0, "keeper", P_fixed_W=1.5, k_cond=0.3, k_sw=0.012, kg_per_kW=2.5, m_base_kg=0.15),
        Converter("heater", 8.0, 8.0, "heater", P_fixed_W=1.0, k_cond=0.05, k_sw=0.008, kg_per_kW=2.0, m_base_kg=0.12),
        Converter("motor", 48.0, P_comp_max_W / 48.0 * 1.5 + 0.5, "motor", P_fixed_W=2.0, k_cond=0.2, k_sw=0.01, kg_per_kW=2.0, m_base_kg=0.2),
        Converter("aux", 5.0, 3.0, "aux", P_fixed_W=1.0, k_cond=0.2, k_sw=0.01, kg_per_kW=2.0, m_base_kg=0.1, redundant=False),
    ]
    if has_stage1:
        if stage1_kind == "ecr":
            conv.append(Converter("hv_mw", 4000.0, P_s1_max_W / 4000.0 * 1.5 + 0.02, "hv_mw", P_fixed_W=4, k_cond=40.0, k_sw=0.02, kg_per_kW=2.5, m_base_kg=0.5))
        else:
            conv.append(Converter("rf_amp", 50.0, P_s1_max_W / 50.0 * 1.4, "aux", P_fixed_W=4, k_cond=0.3, k_sw=0.02, kg_per_kW=2.2, m_base_kg=0.4))
    return PPU(converters=conv)


def load_modes(ppu: PPU, I_d: float, I_mag: float, I_keeper: float, P_s1_W: float, P_comp_W: float,
               heater_I_start: float = 6.0, T_K: float = 300.0) -> dict:
    steady = {"anode": I_d, "magnet": I_mag, "keeper": I_keeper, "motor": P_comp_W / 48.0, "aux": 1.0}
    if P_s1_W > 0:
        hv = "hv_mw" if any(c.name == "hv_mw" for c in ppu.converters) else "rf_amp"
        steady[hv] = P_s1_W / (4000.0 if hv == "hv_mw" else 50.0)
    startup = {"heater": heater_I_start, "keeper": I_keeper * 1.5, "motor": P_comp_W / 48.0 * 1.8, "magnet": I_mag, "aux": 1.0}
    return {"steady": ppu.loads(steady, T_K), "startup": ppu.loads(startup, T_K)}
