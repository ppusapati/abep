"""Uncertainty and sensitivity analysis.

Every fixed prior that decides closure becomes a distribution. For a design point (or a set of
them) we sample N joint realisations, evaluate the full system model each time, and report:
  - P(rfp_compliant), P(abep_closed), quantiles of T/D, power, mass
  - Spearman rank correlation of each input with T/D and with closure (global sensitivity)
  - one-at-a-time tornado at p10/p90 of each input, others at nominal
  - a robustness map: P(closed) over the ECR+Hall design grid

Distributions (triangular: low, mode, high) encode literature spread, not measurement:
replace with test data as it arrives.
"""
from __future__ import annotations
import copy
import itertools
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from .intake import IntakeParams, CompressorParams
from .system import Config, Budgets, evaluate
from .thruster import CARDS
from .aochem import AOParams


FIDELITY = ("analytical", "literature", "breadboard", "qualified")


@dataclass
class Prior:
    name: str
    low: float
    mode: float
    high: float
    target: str            # "intake.<f>" | "comp.<f>" | "card.<f>" | "card.eta_u_max.air" | "stage1.<f>" | "budgets.<f>" | "ao.<f>"
    applies_to: tuple = ("all",)   # restrict to architectures with a stage1 kind, e.g. ("ecr",)
    source: str = "literature-class prior; see README calibration anchors"
    fidelity: str = "literature"   # one of FIDELITY
    kind: str = "epistemic"        # "epistemic" (reducible by test) | "aleatory" (environment)
    units: str = ""
    test_id: str = ""              # filled when a measurement replaces the prior


def provenance_table(priors=None) -> "pd.DataFrame":
    return pd.DataFrame([{"name": p.name, "low": p.low, "mode": p.mode, "high": p.high, "target": p.target,
                          "fidelity": p.fidelity, "kind": p.kind, "source": p.source, "test_id": p.test_id}
                         for p in (priors or DEFAULT_PRIORS)])


def set_measured(priors, name: str, low: float, mode: float, high: float, source: str, test_id: str,
                 fidelity: str = "breadboard"):
    """Replace a prior with a measured range; records provenance. Returns the updated list."""
    out = []
    for p in priors:
        if p.name == name:
            p = Prior(p.name, low, mode, high, p.target, p.applies_to, source, fidelity, p.kind, p.units, test_id)
        out.append(p)
    return out


DEFAULT_PRIORS = [
    Prior("eta_c_specular", 0.30, 0.45, 0.60, "intake.eta_c_specular"),
    Prior("eta_c_diffuse", 0.12, 0.25, 0.35, "intake.eta_c_diffuse"),
    # Joint gas-surface state: one latent variable drives accommodation (hence eta_c and passive CR) AND C_D.
    # Placeholder for the DSMC response surface (eta_c, C_D, CR_passive) = f(geometry, accommodation, AO, angle).
    Prior("surface_state", 0.20, 0.35, 0.80, "joint.surface_state"),   # 0 = fresh specular, 1 = AO-aged diffuse
    Prior("cd_specular", 1.7, 1.9, 2.1, "joint.cd_specular"),
    Prior("cd_diffuse", 2.2, 2.4, 2.7, "joint.cd_diffuse"),
    Prior("intake_mass_per_m2", 1.5, 2.5, 4.0, "intake.mass_per_m2"),
    Prior("comp_area_ratio", 5.0, 10.0, 15.0, "comp.area_ratio"),
    Prior("comp_p_per_mgps_ln", 6.0, 12.0, 30.0, "comp.p_per_mgps_per_ln"),
    Prior("comp_p_base", 20.0, 40.0, 80.0, "comp.p_base_W"),
    Prior("comp_mass_per_ln", 0.3, 0.6, 1.2, "comp.mass_per_ln"),
    Prior("eta_u_max_air", 0.22, 0.30, 0.36, "card.eta_u_max.air"),
    Prior("eta_b_air", 0.55, 0.72, 0.80, "card.eta_b.air"),
    Prior("p_min_hall", 0.008, 0.015, 0.03, "card.p_min_Pa"),
    Prior("eta_v", 0.78, 0.85, 0.90, "card.eta_v"),
    Prior("cos_div", 0.90, 0.95, 0.98, "card.cos_div"),
    Prior("thruster_mass", 3.0, 4.5, 7.0, "card.mass_kg"),
    Prior("s1_eta_u_boost", 0.10, 0.30, 0.40, "stage1.eta_u_boost", ("ecr", "rf")),
    Prior("s1_eta_u_cap", 0.50, 0.65, 0.75, "stage1.eta_u_cap", ("ecr", "rf")),
    Prior("s1_transport_eff", 0.40, 0.80, 1.00, "stage1.transport_eff", ("ecr", "rf")),
    Prior("s1_source_eff", 0.50, 0.65, 0.75, "stage1.source_eff", ("ecr", "rf")),
    Prior("s1_power_fixed", 30.0, 60.0, 120.0, "stage1.power_fixed_W", ("ecr", "rf")),
    Prior("s1_power_per_mgps", 30.0, 60.0, 150.0, "stage1.power_per_mgps_W", ("ecr", "rf")),
    Prior("s1_p_min_ecr", 0.001, 0.002, 0.01, "stage1.p_min_Pa", ("ecr",)),
    Prior("s1_p_min_rf", 0.03, 0.05, 0.15, "stage1.p_min_Pa", ("rf",)),
    Prior("s1_mass", 1.5, 3.0, 5.0, "stage1.mass_kg", ("ecr", "rf")),
    Prior("s1_ic", 0.55, 0.70, 0.90, "stage1.ic", ("ecr", "rf")),
    Prior("ppu_eff", 0.85, 0.90, 0.94, "budgets.ppu_eff"),
    Prior("ppu_mass_base", 2.5, 3.5, 5.5, "budgets.m_ppu_base_kg"),
    Prior("gamma_compressor_wall", 0.02, 0.07, 0.15, "ao.__gamma_comp__"),   # recombination coefficient
]


def _sample_tri(rng, p: Prior, n: int):
    return rng.triangular(p.low, p.mode, p.high, size=n)


_JOINT: dict = {}


def _apply(cfg: Config, card, prior: Prior, val: float):
    t = prior.target
    if t.startswith("joint."):
        _JOINT[t[6:]] = val
        s_ = _JOINT.get("surface_state", 0.35)
        cfg.intake.accommodation = s_
        cfg.intake.cd = (1 - s_) * _JOINT.get("cd_specular", 1.9) + s_ * _JOINT.get("cd_diffuse", 2.4)
        return
    if t.startswith("intake."):
        setattr(cfg.intake, t[7:], val)
    elif t.startswith("comp."):
        setattr(cfg.compressor, t[5:], val)
    elif t.startswith("budgets."):
        setattr(cfg.budgets, t[8:], val)
    elif t == "card.eta_u_max.air":
        card.eta_u_max["air"] = val
    elif t == "card.eta_b.air":
        card.eta_b["air"] = val
    elif t.startswith("card."):
        setattr(card, t[5:], val)
    elif t.startswith("stage1."):
        if card.stage1 is not None:
            setattr(card.stage1, t[7:], val)
    elif t == "ao.__gamma_comp__":
        from . import aochem
        aochem.RECOMB_GAMMA["stainless_steel"] = val


def _relevant(prior: Prior, card) -> bool:
    if prior.applies_to == ("all",):
        return True
    return card.stage1 is not None and card.stage1.kind in prior.applies_to


def monte_carlo(design: dict, n: int = 1000, priors=DEFAULT_PRIORS, seed: int = 1) -> pd.DataFrame:
    """design: {architecture, alt_km, solar, intake_area_m2, comp_ratio, vd_V}."""
    rng = np.random.default_rng(seed)
    base_card = CARDS[design["architecture"]]
    pri = [p for p in priors if _relevant(p, base_card)]
    samples = {p.name: _sample_tri(rng, p, n) for p in pri}
    rows = []
    from . import aochem
    gamma0 = aochem.RECOMB_GAMMA["stainless_steel"]
    for i in range(n):
        card = copy.deepcopy(base_card)
        CARDS[design["architecture"]] = card
        cfg = Config(design["architecture"], design["alt_km"], design["solar"],
                     IntakeParams(area_m2=design["intake_area_m2"]),
                     CompressorParams(ratio=design["comp_ratio"]), vd_V=design.get("vd_V"),
                     budgets=Budgets(), ao=AOParams())
        for p in pri:
            _apply(cfg, card, p, float(samples[p.name][i]))
        r = evaluate(cfg)
        rows.append({**{k: float(samples[k][i]) for k in samples}, "T_over_D": r["T_over_D_air"],
                     "T_air_mN": r["T_air_mN"], "P_total_air_W": r["P_total_air_W"], "m_total_kg": r["m_total_kg"],
                     "ic_thruster": r["ic_thruster"], "rfp_compliant": r["rfp_compliant"], "abep_closed": r["abep_closed"],
                     "technical_compliant": r["technical_compliant"], "technical_closed": r["technical_closed"]})
    CARDS[design["architecture"]] = base_card
    aochem.RECOMB_GAMMA["stainless_steel"] = gamma0
    return pd.DataFrame(rows)


def sensitivity(df: pd.DataFrame, inputs: list[str]) -> pd.DataFrame:
    from scipy.stats import spearmanr
    rows = []
    for k in inputs:
        r_td = spearmanr(df[k], df["T_over_D"]).statistic
        r_cl = spearmanr(df[k], df["technical_closed"].astype(float)).statistic if df["technical_closed"].nunique() > 1 else 0.0
        rows.append({"input": k, "spearman_T_over_D": r_td, "spearman_closure": r_cl})
    return pd.DataFrame(rows).sort_values("spearman_T_over_D", key=np.abs, ascending=False)


def tornado(design: dict, priors=DEFAULT_PRIORS) -> pd.DataFrame:
    """One-at-a-time: each input at its p10 / p90 (triangular), others at mode."""
    base_card = CARDS[design["architecture"]]
    pri = [p for p in priors if _relevant(p, base_card)]
    from . import aochem
    gamma0 = aochem.RECOMB_GAMMA["stainless_steel"]

    def run(overrides: dict):
        card = copy.deepcopy(base_card); CARDS[design["architecture"]] = card
        cfg = Config(design["architecture"], design["alt_km"], design["solar"],
                     IntakeParams(area_m2=design["intake_area_m2"]), CompressorParams(ratio=design["comp_ratio"]),
                     vd_V=design.get("vd_V"), budgets=Budgets(), ao=AOParams())
        for p in pri:
            _apply(cfg, card, p, overrides.get(p.name, p.mode))
        r = evaluate(cfg); CARDS[design["architecture"]] = base_card
        aochem.RECOMB_GAMMA["stainless_steel"] = gamma0
        return r["T_over_D_air"]

    base = run({})
    rows = []
    for p in pri:
        # triangular quantiles
        def q(u):
            c = (p.mode - p.low) / (p.high - p.low)
            return p.low + np.sqrt(u * (p.high - p.low) * (p.mode - p.low)) if u < c else \
                p.high - np.sqrt((1 - u) * (p.high - p.low) * (p.high - p.mode))
        lo, hi = run({p.name: q(0.10)}), run({p.name: q(0.90)})
        rows.append({"input": p.name, "TD_at_p10": lo, "TD_at_p90": hi, "swing": hi - lo, "TD_base": base})
    return pd.DataFrame(rows).sort_values("swing", key=np.abs, ascending=False)


def robustness_map(architecture="hall_ecr", n=150, seed=2, alts=(180, 200, 230), solars=("low", "mean", "high"),
                   areas=(0.5, 1.0, 1.5, 2.0), crs=(500, 2000), vds=(250, 300)) -> pd.DataFrame:
    rows = []
    for alt, sol, a, cr, vd in itertools.product(alts, solars, areas, crs, vds):
        d = {"architecture": architecture, "alt_km": alt, "solar": sol, "intake_area_m2": a, "comp_ratio": cr, "vd_V": vd}
        mc = monte_carlo(d, n=n, seed=seed)
        rows.append({**d, "P_rfp_compliant": mc.rfp_compliant.mean(), "P_closed": mc.abep_closed.mean(),
                     "P_technical_closed": mc.technical_closed.mean(),
                     "TD_p10": mc.T_over_D.quantile(0.10), "TD_p50": mc.T_over_D.quantile(0.50), "TD_p90": mc.T_over_D.quantile(0.90),
                     "P_air_p50_W": mc.P_total_air_W.median(), "m_p50_kg": mc.m_total_kg.median()})
    return pd.DataFrame(rows)


def main(argv=None):
    import argparse, json
    from pathlib import Path
    ap = argparse.ArgumentParser(prog="abep-uq")
    ap.add_argument("--arch", default="hall_ecr"); ap.add_argument("--alt", type=float, default=180)
    ap.add_argument("--solar", default="mean"); ap.add_argument("--area", type=float, default=0.5)
    ap.add_argument("--cr", type=float, default=2000); ap.add_argument("--vd", type=float, default=300)
    ap.add_argument("-n", type=int, default=2000); ap.add_argument("--map", action="store_true")
    ap.add_argument("--map-n", type=int, default=150)
    ap.add_argument("-o", "--out", default="results/uq")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    d = {"architecture": a.arch, "alt_km": a.alt, "solar": a.solar, "intake_area_m2": a.area, "comp_ratio": a.cr, "vd_V": a.vd}
    tag = f"{a.arch}_{int(a.alt)}{a.solar}_A{a.area}_CR{int(a.cr)}_V{int(a.vd)}"
    mc = monte_carlo(d, n=a.n)
    mc.to_csv(out / f"mc_{tag}.csv", index=False)
    inputs = [c for c in mc.columns if c not in ("T_over_D", "T_air_mN", "P_total_air_W", "m_total_kg", "ic_thruster",
                                                  "rfp_compliant", "abep_closed", "technical_compliant", "technical_closed")]
    sens = sensitivity(mc, inputs); sens.to_csv(out / f"sens_{tag}.csv", index=False)
    tor = tornado(d); tor.to_csv(out / f"tornado_{tag}.csv", index=False)
    summ = {"design": d, "n": a.n, "P_rfp_compliant": float(mc.rfp_compliant.mean()), "P_closed": float(mc.abep_closed.mean()),
            "P_technical_compliant": float(mc.technical_compliant.mean()), "P_technical_closed": float(mc.technical_closed.mean()),
            "TD_quantiles": {q: float(mc.T_over_D.quantile(q)) for q in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)},
            "P_air_W_quantiles": {q: float(mc.P_total_air_W.quantile(q)) for q in (0.1, 0.5, 0.9)},
            "mass_kg_quantiles": {q: float(mc.m_total_kg.quantile(q)) for q in (0.1, 0.5, 0.9)}}
    (out / f"summary_{tag}.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))
    pd.set_option("display.width", 200)
    print("\nGlobal sensitivity (Spearman):"); print(sens.round(3).to_string(index=False))
    print("\nTornado (T/D at p10 / p90 of each input, others nominal):"); print(tor.round(3).to_string(index=False))
    if a.map:
        rm = robustness_map(a.arch, n=a.map_n); rm.to_csv(out / f"robustness_{a.arch}.csv", index=False)
        print("\nRobustness map:"); print(rm.sort_values("P_technical_closed", ascending=False).head(20).round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
