"""Phase 6 — UQ & optimisation on the full chain (roadmap items 42–47, 49, 52, 53).

Fidelity hierarchy (item 53): the Monte-Carlo runs on the full physics chain at the *design point* (≈0.3 s/eval:
TPMC ROM, compressor sizing, reservoir balance, global plasma + Hall channel, PPU/thermal/life/BOM). The 26,000 h
mission (≈5 s) is not run per sample; instead a mission ROM calibrated from Phase 5 is used: closure requires
T_air ≥ k_season · D_spacecraft with k_season the worst eclipse-season/solar-phase factor, and the full mission is
run only for the robust-design finalists.
"""
from __future__ import annotations
import copy, itertools, math, json
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from scipy.stats import norm
from .intake import IntakeParams, CompressorParams
from .system import Config, evaluate
from .thruster import CARDS
from .mission_env import Spacecraft, spacecraft_drag
from .atmosphere import atmosphere

# ------------------------------------------------------------------------------------------------ priors
@dataclass
class P6:
    name: str
    low: float; mode: float; high: float
    kind: str            # epistemic | aleatory | tolerance
    group: str           # correlation group (same group -> correlated through a latent normal)
    apply: str           # how to apply (see _apply6)
    source: str = "literature-class prior"
    fidelity: str = "literature"


PRIORS6 = [
    # --- gas-surface / intake (epistemic + tolerance)
    P6("alpha0", 0.55, 0.80, 0.98, "epistemic", "surface", "intake.alpha", "TPMC Maxwell accommodation of fresh coating"),
    P6("phi_c", 1e26, 3e26, 1e28, "epistemic", "surface", "ageing.phi_c", "AO fluence for accommodation drift"),
    P6("L_over_d", 4.0, 5.0, 6.5, "tolerance", "geom", "intake.L_over_d", "honeycomb manufacturing"),
    P6("phi_open", 0.80, 0.85, 0.88, "tolerance", "geom", "intake.phi", "honeycomb open fraction"),
    # --- compressor
    P6("turbo_kS", 0.15, 0.20, 0.28, "epistemic", "comp", "comp.kS", "turbo pumping-speed coefficient"),
    P6("turbo_kK", 0.9, 1.2, 1.6, "epistemic", "comp", "comp.kK", "turbo compression coefficient"),
    P6("gamma_scale", 0.4, 1.0, 2.5, "epistemic", "chem", "chem.gamma_scale", "O wall recombination gamma multiplier"),
    # --- plasma (epistemic) and tolerances
    P6("alpha_anom", 0.12, 0.20, 0.35, "epistemic", "plasma", "hall.alpha_anom", "anomalous transport"),
    P6("L_iz_frac", 0.28, 0.35, 0.45, "epistemic", "plasma", "hall.L_iz_frac", "ionisation-zone fraction (bifurcation!)"),
    P6("rate_scale", 0.7, 1.0, 1.4, "epistemic", "plasma", "chem.rate_scale", "ionisation rate coefficient multiplier"),
    P6("epsc_scale", 0.8, 1.0, 1.3, "epistemic", "plasma", "chem.epsc_scale", "collisional energy loss multiplier"),
    P6("B_gap", 0.018, 0.020, 0.022, "tolerance", "geom", "hall.B", "magnet tolerance ±10 %"),
    P6("channel_gap_mm", 14.0, 15.0, 16.0, "tolerance", "geom", "hall.gap", "channel width tolerance"),
    P6("shielding", 0.02, 0.03, 0.06, "epistemic", "plasma", "hall.shielding", "magnetic shielding quality"),
    # --- electronics / thermal
    P6("ppu_k_sw", 0.009, 0.012, 0.016, "epistemic", "elec", "ppu.k_sw", "switching-loss coefficient"),
    P6("blade_coat_um", 40.0, 50.0, 60.0, "tolerance", "geom", "life.blade_coat", "coating thickness"),
    # --- environment (aleatory)
    P6("f107_season", 0.8, 1.0, 1.25, "aleatory", "env", "env.rho_scale", "density scatter around the MSIS mean"),
    P6("bus_frontal", 0.06, 0.10, 0.16, "epistemic", "sc", "sc.bus_area", "DRDO bus frontal area (unknown)"),
    P6("pointing_sigma", 0.3, 0.5, 1.2, "aleatory", "sc", "sc.pointing", "AOCS pointing"),
]
# correlation between latent normals of groups (surface state drives ageing and alpha0 together, etc.)
GROUP_CORR = {("surface", "surface"): 0.7, ("plasma", "plasma"): 0.3, ("geom", "geom"): 0.0, ("comp", "comp"): 0.5}


def _tri_ppf(u, lo, mo, hi):
    c = (mo - lo) / (hi - lo)
    return np.where(u < c, lo + np.sqrt(u * (hi - lo) * (mo - lo)), hi - np.sqrt((1 - u) * (hi - lo) * (hi - mo)))


def sample_correlated(n: int, priors=PRIORS6, seed: int = 0, independent: bool = False) -> pd.DataFrame:
    """Gaussian copula: within-group latent correlation, then triangular marginals (log-triangular for phi_c).
    independent=True switches the correlation off (required by Sobol estimators)."""
    rng = np.random.default_rng(seed)
    d = len(priors)
    C = np.eye(d)
    for i in range(d):
        for j in range(d):
            if i != j and priors[i].group == priors[j].group and not independent:
                C[i, j] = GROUP_CORR.get((priors[i].group, priors[j].group), 0.0)
    L = np.linalg.cholesky(C + 1e-9 * np.eye(d))
    z = rng.standard_normal((n, d)) @ L.T
    u = norm.cdf(z)
    cols = {}
    for k, p in enumerate(priors):
        if p.name == "phi_c":
            cols[p.name] = 10 ** _tri_ppf(u[:, k], math.log10(p.low), math.log10(p.mode), math.log10(p.high))
        else:
            cols[p.name] = _tri_ppf(u[:, k], p.low, p.mode, p.high)
    return pd.DataFrame(cols)


# ------------------------------------------------------------------------------------------------ apply + evaluate
def evaluate_full(design: dict, x: dict | None = None, sc: Spacecraft | None = None, k_season: float = 1.35) -> dict:
    """design: {area, L_ch, vd, arch}. x: sampled prior values (None = modes). Returns full-chain result + mission ROM."""
    x = x or {p.name: p.mode for p in PRIORS6}
    from . import compressor as _c, plasma_chem as _pc, plasma_devices as _pd, materials as _m, ppu as _ppu, life as _life
    # --- patch physics multipliers (restored after)
    saved = {}
    def patch(mod, name, val):
        saved[(mod, name)] = getattr(mod, name); setattr(mod, name, val)
    rates0 = copy.deepcopy(_pc.RATES); epsc0 = copy.deepcopy(_pc.EPS_C)
    for k in _pc.RATES:
        k0, p, E, ion = _pc.RATES[k]; _pc.RATES[k] = (k0 * x["rate_scale"], p, E, ion)
    for k in _pc.EPS_C:
        a, b = _pc.EPS_C[k]; _pc.EPS_C[k] = (a * x["epsc_scale"], b * x["epsc_scale"])
    gam0 = {k: v.gamma0 for k, v in _m.DB.items()}; gmin0 = {k: v.gamma_min for k, v in _m.DB.items()}
    for k, v in _m.DB.items():
        v.gamma0 *= x["gamma_scale"]; v.gamma_min *= x["gamma_scale"]
    HC = _pd.HallChannel; hc_defaults = (HC.alpha_anom, HC.L_iz_frac)
    HC.alpha_anom = x["alpha_anom"]; HC.L_iz_frac = x["L_iz_frac"]
    DC = _c.DragCompressor; dc_defaults = (DC.turbo_kS, DC.turbo_kK); DC.turbo_kS = x["turbo_kS"]; DC.turbo_kK = x["turbo_kK"]
    CV = _ppu.Converter; cv_default = CV.k_sw; CV.k_sw = x["ppu_k_sw"]
    try:
        gap = x["channel_gap_mm"] * 1e-3
        cfg = Config(design.get("arch", "hall_1stage"), design.get("alt", 200), "mean",
                     IntakeParams(area_m2=design["area"], accommodation=x["alpha0"], use_tpmc=True, L_over_d=x["L_over_d"], phi=x["phi_open"]),
                     CompressorParams(ratio=2000), vd_V=design["vd"], gaspath_physics=True, plasma_physics=True, engineering_physics=True,
                     hall_L_m=design["L_ch"], hall_shielding=x["shielding"], hall_wall_mm=6.0, blade_coating_um=x["blade_coat_um"],
                     xe_aug_hours=design.get("xe_aug_h", 500), hall_B_T=x["B_gap"], hall_r_in_m=0.020, hall_r_out_m=0.020 + gap,
                     s1_power_dc_W=design.get("s1_power"))
        r = evaluate(cfg)
    finally:
        _pc.RATES.clear(); _pc.RATES.update(rates0); _pc.EPS_C.clear(); _pc.EPS_C.update(epsc0)
        for k, v in _m.DB.items():
            v.gamma0 = gam0[k]; v.gamma_min = gmin0[k]
        HC.alpha_anom, HC.L_iz_frac = hc_defaults; DC.turbo_kS, DC.turbo_kK = dc_defaults; CV.k_sw = cv_default
    # --- mission ROM: spacecraft drag at density scatter, ageing-reduced thrust, worst-season factor
    sc = sc or Spacecraft(bus_frontal_m2=x["bus_frontal"], array_area_m2=3.5, pointing_sigma_deg=x["pointing_sigma"])
    sc.bus_frontal_m2 = x["bus_frontal"]; sc.pointing_sigma_deg = x["pointing_sigma"]
    atm = atmosphere(design.get("alt", 200), "mean")
    d = spacecraft_drag(sc, atm["rho"] * x["f107_season"], atm.get("V_rel", atm["V"]), design["area"], r["C_D"])
    from .materials import surface_ageing_alpha
    alpha_end = min(surface_ageing_alpha(x["alpha0"], r["ao_fluence_mission_m2"], phi_c=x["phi_c"]), 1.0)
    from .intake import _tpmc_surface
    surf = _tpmc_surface(atm)
    eta_end = surf(x["L_over_d"], x["phi_open"], alpha_end)["eta_c"]; eta0 = r["eta_c"]
    T_end = r["T_air_mN"] * (eta_end / max(eta0, 1e-9)) * x["f107_season"]        # thrust ~ collected flow
    TD_sc_start = r["T_air_mN"] * x["f107_season"] / (d["D_total_N"] * 1e3)
    TD_sc_end = T_end / (d["D_total_N"] * 1e3)
    mission_ok = (TD_sc_end >= k_season) and r["technical_compliant"] and (r["T_air_mN"] * x["f107_season"] <= 25.0 * 1.15)
    out = {**{k: v for k, v in r.items() if not isinstance(v, (list, dict))}, "D_sc_mN": d["D_total_N"] * 1e3,
           "TD_sc_start": TD_sc_start, "TD_sc_end": TD_sc_end, "alpha_end": alpha_end, "eta_c_end": eta_end,
           "mission_ok_rom": bool(mission_ok), "k_season": k_season}
    out.update(conservation_check(r))
    return out


# ------------------------------------------------------------------------------------------------ conservation
def conservation_check(r: dict, tol: float = 0.03) -> dict:
    """Mass: collected = anode + reservoir leak + compressor leak (physics path); charge: I_d = I_b + I_e;
    power: bus = converters out / eta + control. Returns residuals and a flag; a failed check is never 'feasible'."""
    res = {}
    if r.get("gaspath_model") == "physics":
        # anode flow vs collected: leakage is the only sink in this model -> anode <= collected
        res["mass_resid"] = max(r["mdot_air_mgps"] - r["mdot_incident"] * 1e6 * r["eta_c"], 0.0) / max(r["mdot_air_mgps"], 1e-9) if "mdot_incident" in r else 0.0
    if r.get("plasma_model") == "physics":
        Ib = r.get("I_beam_A", 0.0); Id = r.get("pl_I_d_A", 0.0)
        res["charge_resid"] = abs(Id - Ib / max(r.get("pl_eta_b", 1.0), 1e-9)) / max(Id, 1e-9)
    if r.get("engineering_model") == "physics":
        res["power_resid"] = 0.0 if r["eng_P_bus_steady_W"] >= r["P_thr_air_W"] * 0.9 else abs(r["eng_P_bus_steady_W"] - r["P_thr_air_W"]) / r["P_thr_air_W"]
    ok = all(v <= tol for v in res.values())
    return {**{f"cons_{k}": v for k, v in res.items()}, "chk_conservation": ok}


# ------------------------------------------------------------------------------------------------ MC + Sobol
def monte_carlo6(design: dict, n: int = 200, seed: int = 0, priors=PRIORS6) -> pd.DataFrame:
    X = sample_correlated(n, priors, seed)
    rows = []
    for i in range(n):
        x = X.iloc[i].to_dict()
        try:
            r = evaluate_full(design, x)
        except Exception as e:      # a physics solver failing is itself information
            r = {"mission_ok_rom": False, "technical_compliant": False, "error": str(e)[:60]}
        rows.append({**x, **{k: r.get(k) for k in ("T_air_mN", "T_over_D_air", "TD_sc_start", "TD_sc_end", "eng_P_bus_steady_W", "eng_m_mev_kg",
                                                     "eng_life_hall_h", "eng_blade_coating_life_h", "eng_R_26000h", "technical_compliant",
                                                     "mission_ok_rom", "chk_conservation", "pl_sustained", "error")}})
    return pd.DataFrame(rows)


def sobol(design: dict, n: int = 32, seed: int = 1, priors=PRIORS6, y_key: str = "TD_sc_end") -> pd.DataFrame:
    """Saltelli first-order (Jansen) and total-order indices on the full chain. Cost = n * (d + 2) evaluations."""
    d = len(priors)
    A = sample_correlated(n, priors, seed, independent=True); B = sample_correlated(n, priors, seed + 1000, independent=True)
    def f(X):
        out = []
        for i in range(len(X)):
            try:
                out.append(evaluate_full(design, X.iloc[i].to_dict())[y_key])
            except Exception:
                out.append(np.nan)
        return np.array(out, dtype=float)
    yA, yB = f(A), f(B)
    var = np.nanvar(np.concatenate([yA, yB]))
    rows = []
    for k, p in enumerate(priors):
        AB = A.copy(); AB[p.name] = B[p.name].values
        yAB = f(AB)
        m = ~(np.isnan(yA) | np.isnan(yB) | np.isnan(yAB))
        S1 = np.mean(yB[m] * (yAB[m] - yA[m])) / var
        ST = 0.5 * np.mean((yA[m] - yAB[m]) ** 2) / var
        rows.append({"input": p.name, "kind": p.kind, "S1": S1, "ST": ST})
    return pd.DataFrame(rows).sort_values("ST", ascending=False)


# ------------------------------------------------------------------------------------------------ Pareto + robust
DESIGN_SPACE = {"area": (0.5, 1.0), "L_ch": (0.15, 0.30), "vd": (225.0, 325.0), "xe_aug_h": (200.0, 1500.0)}


def pareto(n_designs: int = 200, seed: int = 3, arch: str = "hall_1stage") -> pd.DataFrame:
    """LHS over the design space at nominal priors; objectives: max (T-D_sc), min P_bus, min MEV, max min(life), min Xe."""
    rng = np.random.default_rng(seed)
    keys = list(DESIGN_SPACE)
    U = (rng.permuted(np.tile(np.arange(n_designs), (len(keys), 1)), axis=1).T + rng.uniform(size=(n_designs, len(keys)))) / n_designs
    rows = []
    for i in range(n_designs):
        dsn = {k: DESIGN_SPACE[k][0] + U[i, j] * (DESIGN_SPACE[k][1] - DESIGN_SPACE[k][0]) for j, k in enumerate(keys)}
        dsn["arch"] = arch
        try:
            r = evaluate_full(dsn)
        except Exception:
            continue
        rows.append({**dsn, "T_minus_D_mN": r["T_air_mN"] - r["D_sc_mN"], "P_bus_W": r["eng_P_bus_steady_W"], "MEV_kg": r["eng_m_mev_kg"],
                     "min_life_h": min(r["eng_life_hall_h"], r["eng_blade_coating_life_h"]), "xe_kg": r["xe_cathode_kg"] + r["xe_aug_kg"],
                     "TD_sc_end": r["TD_sc_end"], "technical_compliant": r["technical_compliant"], "mission_ok_rom": r["mission_ok_rom"]})
    df = pd.DataFrame(rows)
    obj = np.column_stack([-df.T_minus_D_mN, df.P_bus_W, df.MEV_kg, -df.min_life_h, df.xe_kg])
    nd = np.ones(len(df), bool)
    for i in range(len(df)):
        for j in range(len(df)):
            if i != j and np.all(obj[j] <= obj[i]) and np.any(obj[j] < obj[i]):
                nd[i] = False; break
    df["pareto"] = nd
    return df


def robust_design(candidates: pd.DataFrame, n_mc: int = 60, target: float = 0.7, seed: int = 5) -> pd.DataFrame:
    rows = []
    for _, c in candidates.iterrows():
        dsn = {k: c[k] for k in DESIGN_SPACE}; dsn["arch"] = c.get("arch", "hall_1stage")
        mc = monte_carlo6(dsn, n=n_mc, seed=seed)
        rows.append({**dsn, "P_mission_ok": float(mc.mission_ok_rom.mean()), "P_compliant": float(mc.technical_compliant.mean()),
                     "TD_sc_end_p10": float(mc.TD_sc_end.quantile(0.1)), "MEV_p90": float(mc.eng_m_mev_kg.quantile(0.9)),
                     "P_bus_p90": float(mc.eng_P_bus_steady_W.quantile(0.9)), "robust": float(mc.mission_ok_rom.mean()) >= target})
    return pd.DataFrame(rows).sort_values("P_mission_ok", ascending=False)


# ------------------------------------------------------------------------------------------------ data assimilation
def assimilate(design: dict, measurements: list[dict], n: int = 300, seed: int = 7, priors=PRIORS6) -> tuple[list, pd.DataFrame]:
    """ABC rejection: keep prior samples whose predicted outputs fall within the measurement uncertainty.
    measurements: [{"key": "T_air_mN", "value": 18.0, "sigma": 1.5}, ...] at the given design/test conditions.
    Returns updated priors (triangular from posterior 5/50/95 %) and the accepted samples."""
    X = sample_correlated(n, priors, seed)
    keep = []
    for i in range(n):
        x = X.iloc[i].to_dict()
        try:
            r = evaluate_full(design, x)
        except Exception:
            continue
        if all(abs(r.get(m["key"], np.nan) - m["value"]) <= 2 * m["sigma"] for m in measurements):
            keep.append(x)
    post = pd.DataFrame(keep)
    new = []
    for p in priors:
        if len(post) >= 5 and p.name in post:
            q = post[p.name].quantile([0.05, 0.5, 0.95]).values
            new.append(P6(p.name, float(q[0]), float(q[1]), float(q[2]), p.kind, p.group, p.apply,
                          f"assimilated from {len(measurements)} measurements (ABC, {len(post)}/{n} accepted)", "breadboard"))
        else:
            new.append(p)
    return new, post


# ------------------------------------------------------------------------------------------------ fidelity registry
FIDELITY = {
    "atmosphere": ("NRLMSIS 2.1", "validated model"), "intake": ("TPMC free-molecular ROM", "analytical"),
    "compressor": ("turbo/drag Gaede characteristic", "literature"), "reservoir": ("molecular-flow balance", "analytical"),
    "wall_chemistry": ("gamma(T) Arrhenius priors", "literature"), "plasma_global": ("0-D Maxwellian chemistry", "literature"),
    "hall_channel": ("reduced ionisation/acceleration model", "literature-calibrated (Marchioni N2, SPT-100 Xe)"),
    "ecr_rf_source": ("coupling/overdense parametric", "literature"), "interstage": ("magnetised diffusion", "analytical"),
    "cathode": ("Richardson + oxide coverage", "literature"), "thermal": ("7-node lumped", "analytical"),
    "ppu": ("loss-model maps", "literature"), "life": ("sputter + AO + Weibull", "literature"), "mass": ("geometric BOM", "calculated"),
    "orbit": ("secular J2 + energy balance", "analytical"), "radiation": ("parameterised dose-depth", "literature — replace with SPENVIS"),
    "mission_rom": ("k_season closure factor", "calibrated from Phase-5 runs"),
}


def fidelity_report() -> pd.DataFrame:
    return pd.DataFrame([{"module": k, "model": v[0], "fidelity": v[1]} for k, v in FIDELITY.items()])
