"""Mission environment (Phase 5, items 33–38).

Spacecraft drag beyond the ram face (bus, arrays, appendages) with a pointing-error distribution;
plume divergence / CEX backflow onto arrays; J2 secular orbit propagation with atmospheric co-rotation,
drag from the full spacecraft, thrust; beta angle, eclipse fraction, solar-array power available.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
from .constants import MU_EARTH, R_EARTH, AMU, E_CHARGE
from .materials import DB

J2 = 1.08262668e-3
OMEGA_E = 7.2921159e-5
SOLAR_CONST = 1361.0


@dataclass
class Spacecraft:
    mass_kg: float = 150.0
    bus_frontal_m2: float = 0.25        # frontal area beyond the intake (bus, appendages)
    bus_cd: float = 2.2
    array_area_m2: float = 2.0          # total solar array area (both wings)
    array_edge_on: bool = True          # arrays aligned with velocity (thin edge to ram)
    array_thickness_m: float = 0.02
    array_span_m: float = 2.0
    array_eff: float = 0.29
    array_deg_per_yr: float = 0.03
    array_angle_from_thrust_axis_deg: float = 75.0   # angle between thruster axis and array edge as seen from the exit
    array_distance_m: float = 1.2
    pointing_sigma_deg: float = 1.0
    eps_eff: float = 0.90               # battery/PCDU round trip and distribution
    bus_housekeeping_W: float = 120.0
    inc_deg: float = 96.33              # SSO at 200 km (use sso_inclination_deg(alt))
    ltan_h: float = 6.0                 # 06:00 LTAN dawn-dusk
    intake_cd_ref: float = 2.05


def sso_inclination_deg(alt_km: float) -> float:
    """Sun-synchronous inclination: RAAN drift = 360/365.25 deg/day."""
    a = R_EARTH + alt_km * 1e3
    w_s = 2 * math.pi / (365.25 * 86400)
    n = math.sqrt(MU_EARTH / a ** 3)
    cos_i = -w_s / (1.5 * n * J2 * (R_EARTH / a) ** 2)
    return math.degrees(math.acos(cos_i))


ARRAY_AREAL_KG_M2 = 3.2      # deployable rigid panel incl. hinges/booms/mechanism (literature-class)


def worst_eclipse_fraction(sc: "Spacecraft", alt_km: float = 200.0) -> float:
    """Max eclipse fraction over a year for the spacecraft's orbit (sun-synchronous RAAN tracking at its LTAN)."""
    fmax = 0.0
    for day in range(0, 366, 2):
        sun_lon = (day / 365.25 * 360.0) % 360
        dec = 23.44 * math.sin(math.radians(sun_lon))
        raan = (sun_lon + (sc.ltan_h - 12.0) * 15.0) % 360
        fmax = max(fmax, eclipse_fraction(alt_km, beta_angle(sc.inc_deg, raan, sun_lon, dec)))
    return fmax


def array_area_for(P_prop_W: float, sc: "Spacecraft", alt_km: float = 200.0, years: float = 3.0,
                   rho_max_over_design: float = 1.39, P_cap_W: float = 1500.0) -> float:
    """Array area for the worst case the mission actually meets: eclipse season (computed for the orbit), end of
    life, and solar-maximum drag (the propulsion must deliver ~rho_max/rho_design x design thrust, so ~that x power,
    up to the bus cap)."""
    f_ecl = worst_eclipse_fraction(sc, alt_km)
    P_prop_W = min(P_prop_W * rho_max_over_design, P_cap_W)
    eol = 1.0 - sc.array_deg_per_yr * years
    return (P_prop_W + sc.bus_housekeeping_W) / (SOLAR_CONST * sc.array_eff * eol * (1.0 - f_ecl) * sc.eps_eff)


def pointing_factors(sigma_deg: float, n: int = 2000, seed: int = 0) -> dict:
    """Expected cos^2 (collection) and area-exposure factors under a Gaussian pointing error."""
    rng = np.random.default_rng(seed)
    th = np.abs(rng.normal(0.0, sigma_deg, n)) * math.pi / 180.0
    return {"cos2_mean": float(np.mean(np.cos(th) ** 2)), "sin_mean": float(np.mean(np.sin(th))), "theta_p95_deg": float(np.percentile(th, 95) * 180 / math.pi)}


def spacecraft_drag(sc: Spacecraft, rho: float, V_rel: float, intake_area_m2: float, intake_cd: float) -> dict:
    pf = pointing_factors(sc.pointing_sigma_deg)
    q = 0.5 * rho * V_rel ** 2
    D_int = q * intake_cd * intake_area_m2
    D_bus = q * sc.bus_cd * sc.bus_frontal_m2
    if sc.array_edge_on:
        A_arr = sc.array_span_m * sc.array_thickness_m * 2 + sc.array_area_m2 * pf["sin_mean"]
    else:
        A_arr = sc.array_area_m2
    D_arr = q * 2.4 * A_arr
    return {"D_intake_N": D_int, "D_bus_N": D_bus, "D_arrays_N": D_arr, "D_total_N": D_int + D_bus + D_arr,
            "A_arrays_eff_m2": A_arr, "collection_factor": pf["cos2_mean"], "pointing_p95_deg": pf["theta_p95_deg"]}


def plume_interaction(sc: Spacecraft, I_beam_A: float, div_half_deg: float, m_ion_amu: float, Vd: float,
                      n_neutral_exit_m3: float, hours: float) -> dict:
    """Fraction of beam within the array's half-angle cone -> direct impingement; CEX backflow from exit-plane
    neutrals: slow ions born in the plume drift to surfaces at ~ tens of eV. Array coverglass (quartz) erosion."""
    # beam angular distribution ~ Gaussian in angle with sigma = div_half/1.5
    sig = math.radians(div_half_deg) / 1.5
    th_arr = math.radians(sc.array_angle_from_thrust_axis_deg)
    f_direct = math.exp(-0.5 * (th_arr / sig) ** 2)                 # tail fraction reaching array angle
    # CEX production rate in the near plume ~ n_n * sigma_cx * I_beam/e * L ; backflow fraction ~ 0.2
    L_plume = 0.3
    R_cex = n_neutral_exit_m3 * 1.0e-19 * (I_beam_A / E_CHARGE) * L_plume
    flux_arr = 0.2 * R_cex / (4 * math.pi * sc.array_distance_m ** 2) * sc.array_area_m2   # ions/s onto arrays
    E_cex_eV = 30.0
    Y = DB["Quartz"].sputter_yield(E_cex_eV)
    erosion_um = flux_arr * Y * hours * 3600 * (60 * AMU) / (DB["Quartz"].density * sc.array_area_m2) * 1e6
    direct_flux = f_direct * I_beam_A / E_CHARGE
    E_direct = Vd * 0.85
    erosion_direct_um = direct_flux * DB["Quartz"].sputter_yield(E_direct) * hours * 3600 * (60 * AMU) / (DB["Quartz"].density * sc.array_area_m2) * 1e6
    return {"f_beam_direct": f_direct, "cex_ions_per_s_on_arrays": flux_arr, "coverglass_erosion_cex_um": erosion_um,
            "coverglass_erosion_direct_um": erosion_direct_um, "ok": (erosion_um + erosion_direct_um) < 5.0}


def beta_angle(inc_deg: float, raan_deg: float, sun_lon_deg: float, sun_dec_deg: float = 0.0) -> float:
    i, O, ls, d = map(math.radians, (inc_deg, raan_deg, sun_lon_deg, sun_dec_deg))
    return math.degrees(math.asin(math.cos(d) * math.sin(i) * math.sin(O - ls) + math.sin(d) * math.cos(i)))


def eclipse_fraction(alt_km: float, beta_deg: float) -> float:
    a = R_EARTH + alt_km * 1e3
    b = math.radians(abs(beta_deg))
    arg = math.sqrt(max(a ** 2 - R_EARTH ** 2, 0.0)) / (a * math.cos(b)) if math.cos(b) > 0 else 0.0
    if arg >= 1.0 or math.cos(b) == 0.0:
        return 0.0
    return math.acos(arg) / math.pi


def propagate(sc: Spacecraft, alt0_km: float, hours: float, dt_h: float, drag_fn, thrust_fn, power_demand_fn=None,
              raan0_deg: float | None = None, epoch_day: float = 80.0) -> dict:
    """Secular J2 (RAAN drift), altitude from energy balance with full spacecraft drag and thrust, co-rotation,
    beta/eclipse and array power. drag_fn(alt, t_h) -> (D_total, atm dict); thrust_fn(alt, t_h, atm) -> (T, P_bus)."""
    n = int(hours / dt_h)
    alt = alt0_km
    sun_lon0 = (epoch_day / 365.25 * 360.0) % 360
    raan = (sun_lon0 + (sc.ltan_h - 12.0) * 15.0) % 360 if raan0_deg is None else raan0_deg
    rows = []
    for k in range(n):
        t_h = k * dt_h
        a = R_EARTH + alt * 1e3
        nmo = math.sqrt(MU_EARTH / a ** 3)
        raan_dot = -1.5 * nmo * J2 * (R_EARTH / a) ** 2 * math.cos(math.radians(sc.inc_deg))   # rad/s
        raan += math.degrees(raan_dot * dt_h * 3600)
        day = epoch_day + t_h / 24.0
        sun_lon = (day / 365.25 * 360.0) % 360
        sun_dec = 23.44 * math.sin(math.radians(sun_lon))
        beta = beta_angle(sc.inc_deg, raan, sun_lon, sun_dec)
        f_ecl = eclipse_fraction(alt, beta)
        D, atm = drag_fn(alt, t_h)
        yrs0 = t_h / 8766.0
        atm["_P_avail"] = sc.array_area_m2 * SOLAR_CONST * sc.array_eff * (1 - sc.array_deg_per_yr * yrs0) * (1 - f_ecl) * sc.eps_eff
        T, P_bus = thrust_fn(alt, t_h, atm)
        V = math.sqrt(MU_EARTH / a)
        dadt = 2.0 * a ** 1.5 * (T - D) / (sc.mass_kg * math.sqrt(MU_EARTH))
        alt += dadt * dt_h * 3600 / 1e3
        yrs = t_h / 8766.0
        P_arr = sc.array_area_m2 * SOLAR_CONST * sc.array_eff * (1 - sc.array_deg_per_yr * yrs) * math.cos(math.radians(max(0.0, 90 - abs(beta)) * 0.0))  # sun-tracking arrays: full sun when sunlit
        P_avail = P_arr * (1 - f_ecl) * sc.eps_eff
        P_need = P_bus + sc.bus_housekeeping_W
        rows.append({"t_h": t_h, "alt_km": alt, "raan_deg": raan % 360, "beta_deg": beta, "eclipse_frac": f_ecl,
                     "D_mN": D * 1e3, "T_mN": T * 1e3, "P_bus_W": P_bus, "P_need_W": P_need, "P_avail_W": P_avail,
                     "power_margin_W": P_avail - P_need, "rho": atm["rho"]})
        if alt < 150:
            break
    import pandas as pd
    df = pd.DataFrame(rows)
    return {"df": df, "reentered": bool(df.alt_km.iloc[-1] < 150), "min_alt_km": float(df.alt_km.min()),
            "mean_eclipse": float(df.eclipse_frac.mean()), "min_power_margin_W": float(df.power_margin_W.min()),
            "hours_power_short": float((df.power_margin_W < 0).sum() * dt_h), "raan_drift_deg_per_day": float((df.raan_deg.diff().dropna().abs().median()) / (dt_h / 24.0)) if len(df) > 2 else 0.0}
