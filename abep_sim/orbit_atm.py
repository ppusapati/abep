"""Orbit-resolved atmosphere (Phase 1, item 1).

Propagates a circular orbit (Keplerian; J2 arrives in Phase 5) over one or more revolutions, evaluates
NRLMSIS 2.1 at each sub-satellite point with local solar time, F10.7 / F10.7A / Ap, and returns
along-track series and orbit means of: rho, number densities for O, N2, O2, N, He, H, Ar, temperature,
mean molecular mass, relative velocity including atmospheric co-rotation, mean free path, Knudsen number.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from .constants import MU_EARTH, R_EARTH, K_B, AMU, M_SPECIES

OMEGA_E = 7.2921159e-5           # rad/s
SIGMA_COLL = {"O": 1.6e-19, "N2": 4.3e-19, "O2": 4.0e-19, "N": 1.6e-19, "He": 1.5e-19, "H": 1.2e-19, "Ar": 4.1e-19}  # m^2, hard-sphere-ish
M_EXT = {**M_SPECIES, "N": 14.0 * AMU, "He": 4.0 * AMU, "H": 1.0 * AMU, "Ar": 40.0 * AMU}


def _msis_point(date: np.datetime64, lon, lat, alt_km, f107, f107a, ap):
    import pymsis
    out = pymsis.calculate(date, lon, lat, alt_km, f107s=f107, f107as=f107a, aps=[[ap] * 7]).reshape(-1)
    V = pymsis.Variable
    n = {"N2": out[V.N2], "O2": out[V.O2], "O": out[V.O] + out[V.ANOMALOUS_O], "N": out[V.N],
         "He": out[V.HE], "H": out[V.H], "Ar": out[V.AR]}
    return float(out[V.MASS_DENSITY]), {k: float(v) for k, v in n.items()}, float(out[V.TEMPERATURE])


def orbit_atmosphere(alt_km: float, inc_deg: float = 97.4, raan_deg: float = 0.0, epoch: str = "2028-03-21T00:00",
                     f107: float = 150.0, f107a: float | None = None, ap: float = 15.0, n_points: int = 90,
                     revs: float = 1.0, L_ref_m: float = 0.1) -> tuple[pd.DataFrame, dict]:
    """Along-track atmosphere over `revs` revolutions with `n_points` per revolution."""
    f107a = f107 if f107a is None else f107a
    a = R_EARTH + alt_km * 1e3
    V_orb = math.sqrt(MU_EARTH / a)
    T_orb = 2 * math.pi * math.sqrt(a ** 3 / MU_EARTH)
    inc = math.radians(inc_deg); raan = math.radians(raan_deg)
    t0 = np.datetime64(epoch)
    rows = []
    N = int(n_points * revs)
    for k in range(N):
        t = k * T_orb / n_points
        u = 2 * math.pi * (k / n_points)                       # argument of latitude
        # ECI position/velocity for circular orbit
        r_pqw = np.array([math.cos(u), math.sin(u), 0.0]) * a
        v_pqw = np.array([-math.sin(u), math.cos(u), 0.0]) * V_orb
        R = _rot_z(raan) @ _rot_x(inc)
        r = R @ r_pqw; v = R @ v_pqw
        # co-rotating atmosphere velocity and relative velocity
        v_atm = np.cross([0, 0, OMEGA_E], r)
        v_rel = v - v_atm
        # geodetic-ish lat/lon (spherical), GMST approx for longitude
        gmst = _gmst_rad(t0 + np.timedelta64(int(t), "s"))
        lat = math.degrees(math.asin(r[2] / a))
        lon = (math.degrees(math.atan2(r[1], r[0]) - gmst) + 540) % 360 - 180
        date = t0 + np.timedelta64(int(t), "s")
        rho, n, T = _msis_point(date, lon, lat, alt_km, f107, f107a, ap)
        n_tot = sum(n.values())
        m_mean = sum(n[s] * M_EXT[s] for s in n) / n_tot
        lam = 1.0 / (math.sqrt(2) * sum(n[s] * SIGMA_COLL[s] for s in n))
        hours_ut = (date - date.astype("datetime64[D]")) / np.timedelta64(1, "h")
        lst = (hours_ut + lon / 15.0) % 24
        rows.append({"t_s": t, "lat_deg": lat, "lon_deg": lon, "lst_h": lst, "rho": rho, "T": T,
                     **{f"n_{s}": n[s] for s in n}, "m_mean_amu": m_mean / AMU, "V_orb": V_orb,
                     "V_rel": float(np.linalg.norm(v_rel)), "V_rel_ratio": float(np.linalg.norm(v_rel) / V_orb),
                     "mfp_m": lam, "Kn": lam / L_ref_m, "flux_kg_m2_s": rho * float(np.linalg.norm(v_rel))})
    df = pd.DataFrame(rows)
    mass_frac = {}
    for s in ("O", "N2", "O2", "N", "He", "H", "Ar"):
        mass_frac[f"f{s}"] = float((df[f"n_{s}"] * M_EXT[s]).mean() / (df.rho.mean()))
    summ = {"alt_km": alt_km, "inc_deg": inc_deg, "f107": f107, "ap": ap, "T_orb_s": T_orb, "V_orb": V_orb,
            "rho_mean": float(df.rho.mean()), "rho_min": float(df.rho.min()), "rho_max": float(df.rho.max()),
            "V_rel_mean": float(df.V_rel.mean()), "V_rel_min": float(df.V_rel.min()), "V_rel_max": float(df.V_rel.max()),
            "T_mean": float(df["T"].mean()), "m_mean_amu": float(df.m_mean_amu.mean()),
            "mfp_mean_m": float(df.mfp_m.mean()), "Kn_mean": float(df.Kn.mean()), **mass_frac,
            "flux_mean_mgps_per_m2": float(df.flux_kg_m2_s.mean() * 1e6),
            "source": "NRLMSIS 2.1 along-track, circular Keplerian orbit, co-rotating atmosphere"}
    return df, summ


def _rot_x(a):
    c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rot_z(a):
    c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _gmst_rad(date: np.datetime64) -> float:
    jd = (date - np.datetime64("2000-01-01T12:00")) / np.timedelta64(1, "D") + 2451545.0
    T = (jd - 2451545.0) / 36525.0
    g = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * T * T
    return math.radians(g % 360.0)


if __name__ == "__main__":
    import sys, json
    alt = float(sys.argv[1]) if len(sys.argv) > 1 else 200.0
    for f in (70, 150, 230):
        df, s = orbit_atmosphere(alt, f107=f)
        print(json.dumps(s, indent=0))
