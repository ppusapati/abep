"""VLEO atmosphere: density, composition and orbital velocity.

Uses NRLMSISE-00 through `pymsis` when installed. Otherwise falls back to a
tabulated approximation of NRLMSISE-00 mean/low/high solar-activity states
(F10.7 ~ 70 / 150 / 230). The table is deliberately editable — replace with
mission-specific MSIS runs before PDR.
"""
from __future__ import annotations
import math
import numpy as np
from .constants import M_SPECIES, MU_EARTH, R_EARTH, K_B

# altitude_km -> {solar: (rho kg/m3, mass fractions O, N2, O2, T_K)}
_TABLE = {
    180: {"low": (3.3e-10, 0.36, 0.52, 0.12, 750),
          "mean": (5.2e-10, 0.40, 0.49, 0.11, 900),
          "high": (7.8e-10, 0.42, 0.47, 0.11, 1100)},
    200: {"low": (1.5e-10, 0.42, 0.48, 0.10, 800),
          "mean": (2.7e-10, 0.46, 0.44, 0.10, 980),
          "high": (4.6e-10, 0.49, 0.42, 0.09, 1200)},
    230: {"low": (5.5e-11, 0.50, 0.42, 0.08, 830),
          "mean": (1.2e-10, 0.54, 0.38, 0.08, 1030),
          "high": (2.3e-10, 0.58, 0.35, 0.07, 1280)},
}
_SOLAR_F107 = {"low": 70.0, "mean": 150.0, "high": 230.0}


def orbital_velocity(alt_km: float) -> float:
    return math.sqrt(MU_EARTH / (R_EARTH + alt_km * 1e3))


def _interp_table(alt_km: float, solar: str):
    alts = sorted(_TABLE)
    if alt_km <= alts[0]:
        a0 = a1 = alts[0]
    elif alt_km >= alts[-1]:
        a0 = a1 = alts[-1]
    else:
        a0 = max(a for a in alts if a <= alt_km)
        a1 = min(a for a in alts if a >= alt_km)
    r0 = _TABLE[a0][solar]
    r1 = _TABLE[a1][solar]
    if a0 == a1:
        return r0
    f = (alt_km - a0) / (a1 - a0)
    # density interpolates log-linearly, fractions/temperature linearly
    rho = math.exp((1 - f) * math.log(r0[0]) + f * math.log(r1[0]))
    rest = [(1 - f) * x0 + f * x1 for x0, x1 in zip(r0[1:], r1[1:])]
    return (rho, *rest)


_MSIS_CACHE: dict = {}


ATM_VERSION = {"model": "NRLMSIS", "version": 2.1, "epoch": "2028-03-21T12:00", "averaging": "lat -60..60 x 4 LST sectors"}


_FROZEN = {}
FROZEN_EPOCH = "2028-03-21T12:00"


def _frozen():
    """Frozen, versioned NRLMSIS 2.1 scenario dataset shipped in abep_sim/data (150-300 km x F10.7 70..230,
    orbit-averaged, ap 15). The reference behaviour of the simulator; rebuild with `python -m abep_sim.atmosphere build`."""
    if not _FROZEN:
        import os, json, pandas as pd
        d = os.path.join(os.path.dirname(__file__), "data")
        _FROZEN["df"] = pd.read_csv(os.path.join(d, "atmosphere_msis21_v1.csv"))
        _FROZEN["meta"] = json.load(open(os.path.join(d, "atmosphere_msis21_v1.json")))
    return _FROZEN


def _interp_frozen(alt_km: float, f107: float):
    fz = _frozen(); df = fz["df"]
    alts = np.sort(df.alt_km.unique()); fs = np.sort(df.f107.unique())
    if not (alts[0] <= alt_km <= alts[-1] and fs[0] <= f107 <= fs[-1]):
        raise ValueError(f"frozen atmosphere covers {alts[0]}-{alts[-1]} km, F10.7 {fs[0]}-{fs[-1]}; asked {alt_km} km / {f107}")
    def at_f(fv):
        d = df[df.f107 == fv].sort_values("alt_km")
        lr = np.interp(alt_km, d.alt_km, np.log(d.rho))
        return (math.exp(lr), *(float(np.interp(alt_km, d.alt_km, d[c])) for c in ("fO", "fN2", "fO2", "T")))
    i = min(max(int(np.searchsorted(fs, f107)) - 1, 0), len(fs) - 2)
    f0, f1 = fs[i], fs[i + 1]; w = (f107 - f0) / (f1 - f0)
    a, b = at_f(f0), at_f(f1)
    rho = math.exp((1 - w) * math.log(a[0]) + w * math.log(b[0]))
    return tuple(float(v) for v in (rho, *[(1 - w) * a[k] + w * b[k] for k in range(1, 5)]))


def atmosphere(alt_km: float, solar="mean", ap: float = 15.0, lat_deg=None, lon_deg=None,
               date=FROZEN_EPOCH, orbit_average: bool = True, use_msis: bool | None = None) -> dict:
    """Return rho [kg/m3], mass fractions, mean molecular mass [kg], number density [1/m3],
    temperature [K], V_orb [m/s], rho*V flux.

    solar: "low"/"mean"/"high" (F10.7 = 70/150/230) or a numeric F10.7 (F10.7A taken equal).
    With pymsis installed, NRLMSIS 2.1 is used; orbit_average=True averages over latitude
    (-60..60) and local solar time (0..24 h) for a circular orbit, which is what a VLEO drag
    budget needs; pass lat_deg/lon_deg for a point evaluation.
    """
    f107 = _SOLAR_F107[solar] if isinstance(solar, str) else float(solar)
    import os
    mode = os.environ.get("ABEP_ATMOSPHERE", "frozen")                   # frozen (default) | live
    scenario = orbit_average and lat_deg is None and lon_deg is None and ap == 15.0 and date == FROZEN_EPOCH
    if use_msis is None:
        use_msis = not (mode == "frozen" and scenario)
    key = (round(alt_km, 3), f107, ap, lat_deg, lon_deg, date, orbit_average, use_msis)
    if key in _MSIS_CACHE:
        return dict(_MSIS_CACHE[key])
    source = "table"
    rho = fO = fN2 = fO2 = T = None
    if not use_msis and scenario and os.environ.get("ABEP_ALLOW_TABLE_ATMOSPHERE") != "1":
        rho, fO, fN2, fO2, T = _interp_frozen(alt_km, f107)
        source = f"NRLMSIS 2.1 frozen scenario {_frozen()['meta']['sha256_16']}"
    elif use_msis:
        try:
            import pymsis
            import numpy as np
            if orbit_average and lat_deg is None:
                lats = np.array([-60, -40, -20, 0, 20, 40, 60], dtype=float)
                lons = np.array([0, 90, 180, 270], dtype=float)   # LST spread via longitude at fixed UT
            else:
                lats = np.array([0.0 if lat_deg is None else lat_deg]); lons = np.array([0.0 if lon_deg is None else lon_deg])
            out = pymsis.calculate(np.datetime64(date), lons, lats, alt_km, f107s=f107, f107as=f107,
                                   aps=[[ap] * 7])
            out = out.reshape(-1, out.shape[-1])
            V_ = pymsis.Variable
            rho = float(np.nanmean(out[:, V_.MASS_DENSITY]))
            n_n2 = float(np.nanmean(out[:, V_.N2])); n_o2 = float(np.nanmean(out[:, V_.O2]))
            n_o = float(np.nanmean(out[:, V_.O])) + float(np.nanmean(out[:, V_.ANOMALOUS_O]))
            T = float(np.nanmean(out[:, V_.TEMPERATURE]))
            m_tot = n_n2 * M_SPECIES["N2"] + n_o2 * M_SPECIES["O2"] + n_o * M_SPECIES["O"]
            fO, fN2, fO2 = n_o * M_SPECIES["O"] / m_tot, n_n2 * M_SPECIES["N2"] / m_tot, n_o2 * M_SPECIES["O2"] / m_tot
            # He/H/Ar/N are dropped from the composition (<2 % by mass at 180-230 km); rho keeps them
            source = "NRLMSIS 2.1 (pymsis), orbit-averaged" if orbit_average else "NRLMSIS 2.1 (pymsis)"
        except ImportError as e:
            import os
            if os.environ.get("ABEP_ALLOW_TABLE_ATMOSPHERE") != "1":
                raise ImportError("pymsis is required for reproducible results (pip install pymsis). "
                                  "Set ABEP_ALLOW_TABLE_ATMOSPHERE=1 to use the approximate built-in table.") from e
            rho = None
        except Exception as e:
            raise RuntimeError(f"NRLMSIS evaluation failed ({type(e).__name__}: {e}); refusing to fall back silently") from e
    if rho is None:
        sol = solar if isinstance(solar, str) else ("low" if f107 < 110 else "mean" if f107 < 190 else "high")
        rho, fO, fN2, fO2, T = _interp_table(alt_km, sol)
    m_mean = 1.0 / (fO / M_SPECIES["O"] + fN2 / M_SPECIES["N2"] + fO2 / M_SPECIES["O2"])
    n = rho / m_mean
    V = orbital_velocity(alt_km)
    res = {
        "alt_km": alt_km, "solar": solar, "f107": f107, "ap": ap, "rho": rho, "fO": fO, "fN2": fN2, "fO2": fO2,
        "m_mean": m_mean, "n": n, "T": T, "V": V, "flux_kg_m2_s": rho * V,
        "p_ambient_Pa": n * K_B * T, "source": source, "epoch": date, "f107a": f107,
        "n_O": rho * fO / M_SPECIES["O"],
    }
    _MSIS_CACHE[key] = res
    return dict(res)



if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        import json, hashlib, pandas as pd, pymsis
        rows = []
        for f in (70.0, 100.0, 150.0, 190.0, 230.0):
            for h in np.arange(150, 302, 2.0):
                r = atmosphere(float(h), f, use_msis=True)
                rows.append({"alt_km": h, "f107": f, "rho": r["rho"], "fO": r["fO"], "fN2": r["fN2"], "fO2": r["fO2"], "T": r["T"]})
        import os
        out = os.path.join(os.path.dirname(__file__), "data", "atmosphere_msis21_v1.csv")
        pd.DataFrame(rows).to_csv(out, index=False, float_format="%.8e")
        print(out, hashlib.sha256(open(out, "rb").read()).hexdigest()[:16], pymsis.__version__)
