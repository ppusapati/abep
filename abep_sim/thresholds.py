"""PDR-1 acceptance thresholds: P(technical_closed) as a function of the three closure drivers,
with every other prior still sampled from its distribution.

Drivers are imposed as *measured* quantities:
  eta_c_eff   : effective intake collection efficiency after AO exposure (replaces specular/diffuse/accommodation)
  ecr_gain    : net utilisation gain delivered to the Hall stage = eta_u_boost * transport_eff (replaces both)
  cd          : optional third axis
"""
from __future__ import annotations
import copy, itertools
import numpy as np, pandas as pd
from .uncertainty import DEFAULT_PRIORS, _apply, _relevant, _sample_tri
from .intake import IntakeParams, CompressorParams
from .system import Config, Budgets, evaluate
from .thruster import CARDS
from .aochem import AOParams

FIXED = {"eta_c_specular", "eta_c_diffuse", "accommodation", "s1_eta_u_boost", "s1_transport_eff"}


def p_closed(design: dict, eta_c_eff: float, ecr_gain: float, n: int = 300, seed: int = 5, cd: float | None = None) -> dict:
    rng = np.random.default_rng(seed)
    base = CARDS[design["architecture"]]
    pri = [p for p in DEFAULT_PRIORS if _relevant(p, base) and p.name not in FIXED and not (cd is not None and p.name == "cd")]
    samples = {p.name: _sample_tri(rng, p, n) for p in pri}
    from . import aochem
    g0 = aochem.RECOMB_GAMMA["stainless_steel"]
    closed = comp = 0; tds = []
    for i in range(n):
        card = copy.deepcopy(base); CARDS[design["architecture"]] = card
        cfg = Config(design["architecture"], design["alt_km"], design["solar"],
                     IntakeParams(area_m2=design["intake_area_m2"], eta_c_specular=eta_c_eff, eta_c_diffuse=eta_c_eff, accommodation=0.0),
                     CompressorParams(ratio=design["comp_ratio"]), vd_V=design.get("vd_V"), budgets=Budgets(), ao=AOParams())
        if cd is not None:
            cfg.intake.cd = cd
        if card.stage1 is not None:
            card.stage1.eta_u_boost = ecr_gain; card.stage1.transport_eff = 1.0
        for p in pri:
            _apply(cfg, card, p, float(samples[p.name][i]))
        r = evaluate(cfg)
        closed += r["technical_closed"]; comp += r["technical_compliant"]; tds.append(r["T_over_D_air"])
    CARDS[design["architecture"]] = base; aochem.RECOMB_GAMMA["stainless_steel"] = g0
    return {"P_closed": closed / n, "P_compliant": comp / n, "TD_p50": float(np.median(tds))}


def threshold_map(design: dict, eta_cs=(0.35, 0.40, 0.45, 0.50, 0.55), gains=(0.10, 0.15, 0.20, 0.25, 0.30, 0.35),
                  n: int = 1000, reoptimise: bool = True, areas=(0.3, 0.4, 0.5, 0.7, 1.0, 1.5, 2.0), vds=(200, 250, 300),
                  seed: int = 5) -> pd.DataFrame:
    """P(technical_closed) per (eta_c_eff, net ECR gain). With reoptimise=True the intake area and V_d are
    chosen per cell to maximise P(closed) (screened at n//5 samples, winner re-evaluated at n)."""
    rows = []
    for ec, g in itertools.product(eta_cs, gains):
        if not reoptimise:
            rows.append({"eta_c_eff": ec, "ecr_gain": g, **p_closed(design, ec, g, n=n, seed=seed),
                         "area": design["intake_area_m2"], "vd": design.get("vd_V")})
            continue
        best = None
        for a, vd in itertools.product(areas, vds):
            d = {**design, "intake_area_m2": a, "vd_V": vd}
            r = p_closed(d, ec, g, n=max(n // 5, 60), seed=seed)
            if best is None or r["P_closed"] > best["P_closed"]:
                best = {**r, "area": a, "vd": vd}
        d = {**design, "intake_area_m2": best["area"], "vd_V": best["vd"]}
        r = p_closed(d, ec, g, n=n, seed=seed + 1)
        rows.append({"eta_c_eff": ec, "ecr_gain": g, **r, "area": best["area"], "vd": best["vd"]})
    return pd.DataFrame(rows)


def main(argv=None):
    import argparse
    from pathlib import Path
    ap = argparse.ArgumentParser(prog="abep-thresholds")
    ap.add_argument("--arch", default="hall_ecr"); ap.add_argument("--alt", type=float, default=180)
    ap.add_argument("--solar", default="mean"); ap.add_argument("--cr", type=float, default=2000)
    ap.add_argument("-n", type=int, default=1000); ap.add_argument("--no-reopt", action="store_true")
    ap.add_argument("--eta-c", type=float, nargs="+", default=[0.35, 0.40, 0.45, 0.50, 0.55])
    ap.add_argument("--gain", type=float, nargs="+", default=[0.10, 0.15, 0.20, 0.25, 0.30, 0.35])
    ap.add_argument("-o", "--out", default="results/uq")
    a = ap.parse_args(argv)
    d = {"architecture": a.arch, "alt_km": a.alt, "solar": a.solar, "intake_area_m2": 0.5, "comp_ratio": a.cr, "vd_V": 300}
    df = threshold_map(d, eta_cs=a.eta_c, gains=a.gain, n=a.n, reoptimise=not a.no_reopt)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tag = f"{a.arch}_{int(a.alt)}{a.solar}_n{a.n}{'_fixed' if a.no_reopt else '_reopt'}"
    df.to_csv(out / f"thresholds_{tag}.csv", index=False)
    print(f"P(technical_closed) — {tag}")
    print(df.pivot(index="eta_c_eff", columns="ecr_gain", values="P_closed").round(2).to_string())
    print("\nchosen area/Vd:")
    print(df.assign(s=df.area.astype(str) + "/" + df.vd.astype(str)).pivot(index="eta_c_eff", columns="ecr_gain", values="s").to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
