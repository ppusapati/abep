"""UQ on the modular architecture engine (document 16, item 38).

For a fixed design (architecture, operating variables, intake area, reservoir pressure, array area) sample:
  epistemic: anomalous transport alpha_anom, ionisation-zone fraction, ionisation-rate scale, collisional-loss scale,
             intake accommodation (Maxwell alpha), ECR transported-current scale (assisted architectures)
  aleatory : bus frontal area (DRDO spacecraft unknown), AOCS pointing
and re-run the same propulsion physics at mean / solar-min / solar-max captured flow (design point from a cold start,
off-design by continuation), with the bus-power cap applied at solar max. Closure metric per sample:
  r = min( T/D (mean), T_lo/D_lo, T_hi/D_hi ),  mission closes with margin if r >= 1.1.
Returns samples, P(r >= 1), P(r >= 1.1), quantiles and Spearman sensitivities.
"""
from __future__ import annotations
import copy, math
import numpy as np
import pandas as pd
from .archengine import enumerate_architectures, arch_name, _propulsion, make_gas_fn, HALL_OVERRIDES
from .atmosphere import atmosphere
from .mission_env import Spacecraft, spacecraft_drag
from . import plasma_chem as PC
from . import plasma_devices as PD

PRIORS = {  # name: (low, mode, high, kind)
    "alpha_anom": (0.75, 0.88, 1.00, "epistemic"),
    "L_iz_frac": (0.33, 0.40, 0.47, "epistemic"),
    "rate_scale": (0.80, 1.00, 1.25, "epistemic"),
    "epsc_scale": (0.85, 1.00, 1.20, "epistemic"),
    "accommodation": (0.60, 0.80, 0.95, "epistemic"),
    "ecr_scale": (0.5, 1.0, 2.0, "epistemic"),
    "bus_frontal": (0.06, 0.10, 0.16, "aleatory"),
    "pointing": (0.3, 0.5, 1.0, "aleatory"),
}


def _tri(rng, lo, mo, hi, n):
    return rng.triangular(lo, mo, hi, n)


def evaluate_sample(a, x, area, p_level, A_array, P_cap, xs: dict, alt=200.0, eta_ppu=0.9, P_mag=25.0) -> dict:
    alpha_q = round(xs["accommodation"] / 0.05) * 0.05                     # reuse cached gas states
    gf = make_gas_fn(alpha=alpha_q, alt=alt)
    gas = gf(area, p_level)
    rates0 = dict(PC.RATES); eps0 = dict(PC.EPS_C)
    for k, (k0, p, E, ion) in list(PC.RATES.items()):
        PC.RATES[k] = (k0 * xs["rate_scale"], p, E, ion)
    for k, (aa, bb) in list(PC.EPS_C.items()):
        PC.EPS_C[k] = (aa * xs["epsc_scale"], bb * xs["epsc_scale"])
    HALL_OVERRIDES.clear(); HALL_OVERRIDES.update({"alpha_anom": xs["alpha_anom"], "L_iz_frac": xs["L_iz_frac"]})
    x2 = dict(x)
    if "P_ion" in x2:
        x2["P_ion"] = x2["P_ion"] * xs["ecr_scale"]          # transported-current uncertainty as an effective power scale
    try:
        atm = atmosphere(alt, "mean")
        r_lo = atmosphere(alt, "low")["rho"] / atm["rho"]; r_hi = atmosphere(alt, "high")["rho"] / atm["rho"]
        sc = Spacecraft(bus_frontal_m2=xs["bus_frontal"], array_area_m2=A_array, pointing_sigma_deg=xs["pointing"])
        D = spacecraft_drag(sc, atm["rho"], atm.get("V_rel", atm["V"]), area, gas["C_D"])["D_total_N"]

        def run(scale, start):
            g2 = dict(gas); g2["mdot_air"] = gas["mdot_air"] * scale; g2["p_in"] = gas["p_in"] * scale
            HALL_OVERRIDES["start"] = start
            try:
                q = _propulsion(a, g2, x2)
            except ValueError:
                return 0.0, 0.0
            P = (q["P_acc_W"] + q["P_ion_W"] + q["P_neut_W"] + P_mag + gas["comp_power"] + 5.0) / eta_ppu + 12.0
            return q["T_N"], P

        T0, P0 = run(1.0, "cold")
        # component life at the design point (accelerator, neutralizer, blade/intake coatings)
        HALL_OVERRIDES["start"] = "cold"
        try:
            q0 = _propulsion(a, gas, x2)
            life = min(list(q0["life_items"].values()) + [gas["blade_life_h"], gas["intake_life_h"]])
        except ValueError:
            life = 0.0
        T_lo, _ = run(r_lo, "hot") if T0 > 0 else (0.0, 0.0)
        T_hi, P_hi = run(r_hi, "hot") if T0 > 0 else (0.0, 0.0)
        if P_hi > P_cap:
            T_hi *= P_cap / P_hi
        ratio = min(T0 / D, T_lo / (D * r_lo), T_hi / (D * r_hi)) if D > 0 else 0.0
        return {"T_mN": T0 * 1e3, "P_bus_W": P0, "T_lo_mN": T_lo * 1e3, "T_hi_mN": T_hi * 1e3, "D_mN": D * 1e3,
                "ratio_min": ratio, "ignited": T0 > 0, "life_h": life, "success": bool(ratio >= 1.0 and life >= 15000.0), "limit": ["mean", "solar_min", "solar_max"][int(np.argmin(
                    [T0 / D, T_lo / (D * r_lo), T_hi / (D * r_hi)]))] if T0 > 0 else "no_ignition"}
    finally:
        PC.RATES.clear(); PC.RATES.update(rates0); PC.EPS_C.clear(); PC.EPS_C.update(eps0); HALL_OVERRIDES.clear()


def run_uq(arch: str, x: dict, area: float, p_level: float, A_array: float, P_cap: float, n: int = 200, seed: int = 1,
           alt: float = 200.0) -> tuple[pd.DataFrame, dict]:
    from scipy.stats import spearmanr
    a = {arch_name(z): z for z in enumerate_architectures()}[arch]
    rng = np.random.default_rng(seed)
    S = {k: _tri(rng, lo, mo, hi, n) for k, (lo, mo, hi, _) in PRIORS.items()}
    rows = []
    for i in range(n):
        xs = {k: float(S[k][i]) for k in S}
        rows.append({**xs, **evaluate_sample(a, x, area, p_level, A_array, P_cap, xs, alt)})
    df = pd.DataFrame(rows)
    sens = {}
    for k in PRIORS:
        if df[k].std() > 0 and df.ratio_min.std() > 0:
            sens[k] = float(spearmanr(df[k], df.ratio_min).statistic)
    summ = {"arch": arch, "x": x, "area": area, "p_level": p_level, "A_array": A_array, "P_cap": P_cap, "n": n,
            "P_ignite": float(df.ignited.mean()), "P_close": float((df.ratio_min >= 1.0).mean()),
            "P_close_margin": float((df.ratio_min >= 1.1).mean()),
            "P_success": float(df.success.mean()), "P_life_ok": float((df.life_h >= 15000.0).mean()),
            "life_q": {q: float(df.life_h.quantile(q)) for q in (0.1, 0.5, 0.9)},
            "ratio_q": {q: float(df.ratio_min.quantile(q)) for q in (0.1, 0.5, 0.9)},
            "limit_counts": df.limit.value_counts().to_dict(),
            "spearman": dict(sorted(sens.items(), key=lambda kv: -abs(kv[1])))}
    return df, summ


def sobol_modular(arch: str, x: dict, area: float, p_level: float, A_array: float, P_cap: float, n: int = 64,
                  seed: int = 3, n_boot: int = 300, alt: float = 200.0) -> pd.DataFrame:
    """Saltelli sampling with Jansen first-order and total-order estimators on r = min(T/D over the cycle), with
    bootstrap 90 % confidence intervals (document 16, item 37). Inputs sampled independently (Sobol requires it);
    report negative / >1 indices as numerical noise, not physics. Cost: n (d + 2) evaluations."""
    a = {arch_name(z): z for z in enumerate_architectures()}[arch]
    rng = np.random.default_rng(seed)
    names = [k for k in PRIORS if not (k == "ecr_scale" and "P_ion" not in x)]
    def sample(m):
        return pd.DataFrame({k: _tri(rng, *PRIORS[k][:3], m) for k in names})
    A = sample(n); B = sample(n)
    def f(X):
        return np.array([evaluate_sample(a, x, area, p_level, A_array, P_cap, {**{k: PRIORS[k][1] for k in PRIORS}, **X.iloc[i].to_dict()}, alt)["ratio_min"]
                         for i in range(len(X))])
    yA, yB = f(A), f(B)
    yAB = {}
    for k in names:
        AB = A.copy(); AB[k] = B[k].values; yAB[k] = f(AB)
    rows = []
    for k in names:
        def est(idx):
            ya, yb, yab = yA[idx], yB[idx], yAB[k][idx]
            V = np.var(np.concatenate([ya, yb]))
            if V <= 0: return 0.0, 0.0
            S1 = (V - 0.5 * np.mean((yb - yab) ** 2)) / V         # Jansen
            ST = 0.5 * np.mean((ya - yab) ** 2) / V
            return S1, ST
        S1, ST = est(np.arange(n))
        bs = np.array([est(rng.integers(0, n, n)) for _ in range(n_boot)])
        rows.append({"input": k, "kind": PRIORS[k][3], "S1": S1, "S1_lo": np.percentile(bs[:, 0], 5), "S1_hi": np.percentile(bs[:, 0], 95),
                     "ST": ST, "ST_lo": np.percentile(bs[:, 1], 5), "ST_hi": np.percentile(bs[:, 1], 95)})
    return pd.DataFrame(rows).sort_values("ST", ascending=False)
