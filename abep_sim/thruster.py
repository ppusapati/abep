"""Thruster architecture cards and a unified electrostatic performance model.

Model (per species s, anode flow mdot_s):
    ion current       I_b   = sum_s eta_u_s * mdot_s * e / m_s
    ion velocity      v_s   = sqrt(2 e Vd eta_v / m_s)
    thrust            T     = cos_div * sum_s eta_u_s * mdot_s * v_s
    discharge power   P_d   = (I_b / eta_b) * Vd
    Isp               = T / (g0 * (mdot_anode + mdot_cathode))
Utilisation eta_u is a log-sigmoid of inlet pressure around p_min (discharge
starves below it), scaled by eta_u_max(gas), and optionally lifted by a
pre-ioniser stage that costs its own power and mass.

Every number on a card is a *prior* to be replaced by test data. The cards are
calibrated to: Marchioni & Cappelli 2021 (extended-channel Hall on N2, ~2 mg/s,
17-22 mN, 500-800 W); SITAEL RAM-HET dual-stage (N2/O2, ~6 mN class);
AMPCAT (0.8 A on 0.1 mg/s air, 145 W); ONERA ECRA (~1 mN / 30-50 W);
Michigan Helicon-Hall (RF added: eta_u up slightly, T/P down).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional
from .constants import E_CHARGE, G0, M_SPECIES


@dataclass
class Stage1:
    """Pre-ioniser (ECR or RF) in front of the accelerator."""
    kind: str                     # "ecr" | "rf"
    p_min_Pa: float               # below this the stage cannot sustain plasma
    power_fixed_W: float          # generator floor
    power_per_mgps_W: float       # scales with throughput
    source_eff: float             # DC->deposited RF/MW efficiency
    eta_u_boost: float            # additive lift to eta_u (saturates at eta_u_cap)
    eta_u_cap: float
    mass_kg: float
    ic: float                     # indigenous-content estimate of the stage hardware
    transport_eff: float = 1.0    # fraction of pre-ionised plasma that survives the interstage region


@dataclass
class Cathode:
    kind: str                     # "xe_hollow" | "mw_air" | "none"
    xe_flow_mgps: float = 0.0
    air_flow_mgps: float = 0.0
    power_W: float = 0.0
    o_life_h: float = 1e9         # erosion/poisoning-limited life when exposed to O plasma


@dataclass
class Card:
    name: str
    family: str                   # hall | gridded | gridless_ecr | helicon
    hall: bool                    # counts for "Hall effect preferable"
    eta_u_max: dict               # {"Xe":..,"air":..}
    p_min_Pa: float               # accelerator/discharge minimum inlet pressure (air)
    p_width_dec: float            # sigmoid width in decades
    eta_b: dict                   # current utilisation {"Xe":..,"air":..}
    eta_v: float                  # voltage utilisation
    cos_div: float
    vd_default_V: float
    p_magnet_W: float
    mass_kg: float                # thruster + magnetic circuit
    ic_thruster: float
    cathode: Cathode
    stage1: Optional[Stage1] = None
    o_life_h: dict = field(default_factory=dict)   # component -> life in O plasma
    tpl_note: str = ""
    o2_diss_fraction: float = 0.5   # fraction of ionised O2 mass that pays the 5.12 eV dissociation sink

    def utilisation(self, gas: str, p_in_Pa: float) -> float:
        base = self.eta_u_max[gas]
        if gas == "Xe":
            return base
        x = (math.log10(max(p_in_Pa, 1e-12)) - math.log10(self.p_min_Pa)) / self.p_width_dec
        s = 1.0 / (1.0 + math.exp(-4.0 * x))
        eta = base * s
        if self.stage1 is not None:
            x1 = (math.log10(max(p_in_Pa, 1e-12)) - math.log10(self.stage1.p_min_Pa)) / self.p_width_dec
            s1 = 1.0 / (1.0 + math.exp(-4.0 * x1))
            eta = min(self.stage1.eta_u_cap, eta + self.stage1.eta_u_boost * self.stage1.transport_eff * s1)
        return eta


def _stage1(kind: str) -> Stage1:
    if kind == "ecr":
        return Stage1("ecr", p_min_Pa=2e-3, power_fixed_W=60, power_per_mgps_W=60,
                      source_eff=0.65, eta_u_boost=0.30, eta_u_cap=0.65, mass_kg=3.0, ic=0.70)
    if kind == "rf":
        return Stage1("rf", p_min_Pa=5e-2, power_fixed_W=50, power_per_mgps_W=70,
                      source_eff=0.75, eta_u_boost=0.25, eta_u_cap=0.60, mass_kg=2.5, ic=0.80)
    raise ValueError(kind)


XE_CATHODE = Cathode("xe_hollow", xe_flow_mgps=0.05, power_W=40.0, o_life_h=1e9)
MW_AIR_CATHODE = Cathode("mw_air", air_flow_mgps=0.10, power_W=145.0, o_life_h=3000.0)

CARDS: dict[str, Card] = {}


def _add(c: Card):
    CARDS[c.name] = c


_add(Card("hall_1stage", "hall", True,
          eta_u_max={"Xe": 0.90, "air": 0.30}, p_min_Pa=1.5e-2, p_width_dec=0.5,
          eta_b={"Xe": 0.75, "air": 0.72}, eta_v=0.85, cos_div=0.95, vd_default_V=250,
          p_magnet_W=25, mass_kg=4.0, ic_thruster=0.85, cathode=XE_CATHODE,
          o_life_h={"channel_shielded": 20000, "anode": 30000},
          tpl_note="Extended-channel, magnetically shielded Hall; Xe-fed LaB6 cathode"))

_add(Card("hall_ecr", "hall", True,
          eta_u_max={"Xe": 0.90, "air": 0.30}, p_min_Pa=1.5e-2, p_width_dec=0.5,
          eta_b={"Xe": 0.75, "air": 0.72}, eta_v=0.85, cos_div=0.95, vd_default_V=250,
          p_magnet_W=35, mass_kg=4.5, ic_thruster=0.80, cathode=XE_CATHODE,
          stage1=_stage1("ecr"),
          o_life_h={"channel_shielded": 20000, "anode": 30000, "ecr_chamber": 40000},
          tpl_note="ECR pre-ioniser (2.45 GHz) + shielded Hall accelerator"))

_add(Card("hall_rf", "hall", True,
          eta_u_max={"Xe": 0.90, "air": 0.30}, p_min_Pa=1.5e-2, p_width_dec=0.5,
          eta_b={"Xe": 0.75, "air": 0.72}, eta_v=0.85, cos_div=0.95, vd_default_V=250,
          p_magnet_W=35, mass_kg=4.5, ic_thruster=0.82, cathode=XE_CATHODE,
          stage1=_stage1("rf"),
          o_life_h={"channel_shielded": 20000, "anode": 30000, "rf_liner": 40000},
          tpl_note="RF/helicon pre-ioniser + shielded Hall accelerator"))

_add(Card("hall_1stage_mwcat", "hall", True,
          eta_u_max={"Xe": 0.90, "air": 0.30}, p_min_Pa=1.5e-2, p_width_dec=0.5,
          eta_b={"Xe": 0.75, "air": 0.72}, eta_v=0.85, cos_div=0.95, vd_default_V=250,
          p_magnet_W=25, mass_kg=4.0, ic_thruster=0.85, cathode=MW_AIR_CATHODE,
          o_life_h={"channel_shielded": 20000, "anode": 30000, "mw_cathode": 3000},
          tpl_note="Single-stage Hall with air-breathing microwave cathode (no Xe cathode flow)"))

_add(Card("rf_gridded_ion", "gridded", False,
          eta_u_max={"Xe": 0.92, "air": 0.55}, p_min_Pa=5e-2, p_width_dec=0.5,
          eta_b={"Xe": 0.85, "air": 0.60}, eta_v=0.95, cos_div=0.98, vd_default_V=1200,
          p_magnet_W=0, mass_kg=6.0, ic_thruster=0.50, cathode=XE_CATHODE,
          o_life_h={"grids": 6000},
          tpl_note="RF ion thruster (RIT-class); eta_b here folds in RF generator efficiency"))

_add(Card("ecr_gridless", "gridless_ecr", False,
          eta_u_max={"Xe": 0.70, "air": 0.45}, p_min_Pa=3e-3, p_width_dec=0.5,
          eta_b={"Xe": 0.22, "air": 0.15}, eta_v=1.0, cos_div=0.85, vd_default_V=150,
          p_magnet_W=15, mass_kg=5.0, ic_thruster=0.60, cathode=Cathode("none"),
          o_life_h={"chamber_wall": 60000},
          tpl_note="Grid-less ECR magnetic nozzle (ECRA-class); Vd = ion energy proxy, eta_b = power coupling"))

_add(Card("helicon", "helicon", False,
          eta_u_max={"Xe": 0.60, "air": 0.40}, p_min_Pa=8e-2, p_width_dec=0.5,
          eta_b={"Xe": 0.12, "air": 0.08}, eta_v=1.0, cos_div=0.80, vd_default_V=120,
          p_magnet_W=40, mass_kg=6.0, ic_thruster=0.70, cathode=Cathode("none"),
          o_life_h={"liner": 60000},
          tpl_note="Helicon/IPT magnetic nozzle; Vd = ion energy proxy"))


def species_flows(mdot_air: float, atm: dict) -> dict:
    return {"O": mdot_air * atm["fO"], "N2": mdot_air * atm["fN2"], "O2": mdot_air * atm["fO2"]}


def performance(card: Card, atm: dict, mdot_air: float, p_in_Pa: float,
                vd_V: Optional[float] = None, mdot_xe_anode: float = 0.0) -> dict:
    """Thrust, Isp, power for a given anode flow split (air + optional Xe)."""
    vd = card.vd_default_V if vd_V is None else vd_V
    eta_u_air = card.utilisation("air", p_in_Pa)
    eta_u_xe = card.utilisation("Xe", p_in_Pa)
    flows = species_flows(mdot_air, atm)
    T = 0.0
    I_b_air = 0.0
    for s, md in flows.items():
        m = M_SPECIES[s]
        v = math.sqrt(2 * E_CHARGE * vd * card.eta_v / m)
        T += card.cos_div * eta_u_air * md * v
        I_b_air += eta_u_air * md * E_CHARGE / m
    I_b_xe = 0.0
    if mdot_xe_anode > 0:
        m = M_SPECIES["Xe"]
        v = math.sqrt(2 * E_CHARGE * vd * card.eta_v / m)
        T += card.cos_div * eta_u_xe * mdot_xe_anode * v
        I_b_xe = eta_u_xe * mdot_xe_anode * E_CHARGE / m
    # blended current utilisation weighted by beam current
    tot_b = I_b_air + I_b_xe
    eta_b = ((I_b_air * card.eta_b["air"] + I_b_xe * card.eta_b["Xe"]) / tot_b) if tot_b > 0 else card.eta_b["air"]
    P_d = (tot_b / eta_b) * vd if tot_b > 0 else 0.0
    # O2 dissociation energy sink (from aochem.inlet_composition), applied to ionised O2 mass
    P_diss = eta_u_air * mdot_air * atm.get("diss_sink_J_per_kg", 0.0) * card.o2_diss_fraction
    P_d += P_diss
    P_s1 = 0.0
    if card.stage1 is not None:
        dep = card.stage1.power_fixed_W + card.stage1.power_per_mgps_W * (mdot_air * 1e6)
        P_s1 = dep / card.stage1.source_eff
    P_thr = P_d + P_s1 + card.p_magnet_W + card.cathode.power_W
    mdot_tot = mdot_air + mdot_xe_anode + card.cathode.xe_flow_mgps * 1e-6 + card.cathode.air_flow_mgps * 1e-6
    isp = T / (G0 * mdot_tot) if mdot_tot > 0 else 0.0
    return {"T_N": T, "Isp_s": isp, "P_discharge_W": P_d, "P_stage1_W": P_s1,
            "P_thruster_W": P_thr, "eta_u_air": eta_u_air, "I_beam_A": tot_b,
            "eta_b": eta_b, "vd_V": vd, "P_diss_W": P_diss,
            "eta_thruster": (T ** 2 / (2 * mdot_tot * P_thr)) if (P_thr > 0 and mdot_tot > 0) else 0.0}


def xe_for_thrust(card: Card, atm: dict, mdot_air: float, p_in_Pa: float, T_target_N: float,
                  vd_V: Optional[float] = None) -> float:
    """Anode Xe flow [kg/s] needed to top air thrust up to T_target (0 if already met)."""
    base = performance(card, atm, mdot_air, p_in_Pa, vd_V)
    if base["T_N"] >= T_target_N:
        return 0.0
    vd = card.vd_default_V if vd_V is None else vd_V
    v_xe = math.sqrt(2 * E_CHARGE * vd * card.eta_v / M_SPECIES["Xe"])
    per_kg = card.cos_div * card.utilisation("Xe", p_in_Pa) * v_xe
    return (T_target_N - base["T_N"]) / per_kg
