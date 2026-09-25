"""Design-space sweep: cartesian product over a YAML grid -> CSV + summary + plots."""
from __future__ import annotations
import itertools
import sys
from pathlib import Path
import pandas as pd
import yaml
from .intake import IntakeParams, CompressorParams
from .system import Config, Budgets, evaluate
from .thruster import CARDS

DEFAULT_GRID = {
    "architectures": list(CARDS),
    "alt_km": [180, 200, 230],
    "solar": ["low", "mean", "high"],
    "intake_area_m2": [0.5, 1.0, 1.5, 2.0, 3.0],
    "accommodation": [0.3, 0.7],
    "comp_ratio": [100, 500, 2000],
    "vd_V": [120, 160, 200, 250, 300],
    "T_required_mN": [None],
    "body_area_m2": [0.0],
}


def apply_card_overrides(overrides: dict):
    """grid['card_overrides'] = {card_name: {field: value, stage1: {field: value}, cathode: {...}}}"""
    import copy, dataclasses
    for name, ov in (overrides or {}).items():
        card = copy.deepcopy(CARDS[name])
        for k, v in ov.items():
            cur = getattr(card, k)
            if dataclasses.is_dataclass(cur) and isinstance(v, dict):
                for kk, vv in v.items():
                    setattr(cur, kk, vv)
            elif isinstance(cur, dict) and isinstance(v, dict):
                cur.update(v)
            else:
                setattr(card, k, v)
        CARDS[name] = card


def run_grid(grid: dict) -> pd.DataFrame:
    apply_card_overrides(grid.get("card_overrides"))
    g = {**DEFAULT_GRID, **grid}
    keys = ["architectures", "alt_km", "solar", "intake_area_m2", "accommodation", "comp_ratio",
            "vd_V", "T_required_mN", "body_area_m2"]
    rows = []
    for arch, alt, sol, area, acc, cr, vd, treq, body in itertools.product(*(g[k] for k in keys)):
        cfg = Config(architecture=arch, alt_km=alt, solar=sol,
                     intake=IntakeParams(area_m2=area, accommodation=acc),
                     compressor=CompressorParams(ratio=cr), vd_V=vd, T_required_mN=treq, body_area_m2=body,
                     budgets=Budgets(**g.get("budgets", {})))
        rows.append(evaluate(cfg))
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> str:
    out = []
    n = len(df)
    out.append(f"{n} configurations evaluated; {int(df.rfp_compliant.sum())} RFP-compliant "
               f"(12 mN sustained on air, 25 mN peak, power, mass, life, IC, compressor); "
               f"{int(df.abep_closed.sum())} ABEP-closed (RFP-compliant AND T > D on air).\n")
    out.append("RFP-compliant count by architecture:")
    out.append(df.groupby("architecture").rfp_compliant.sum().sort_values(ascending=False).to_string())
    out.append(f"\nTechnical-only (no IC checks): {int(df.technical_compliant.sum())} compliant, {int(df.technical_closed.sum())} closed.")
    out.append("Technical-closed count by architecture:")
    out.append(df.groupby("architecture").technical_closed.sum().sort_values(ascending=False).to_string())
    out.append("\nABEP-closed count by architecture:")
    out.append(df.groupby("architecture").abep_closed.sum().sort_values(ascending=False).to_string())
    out.append("\nABEP-closed configurations by altitude / solar:")
    closed = df[df.abep_closed]
    if closed.empty:
        out.append("  none")
    else:
        out.append(closed.groupby(["architecture", "alt_km", "solar"]).size().to_string())
    out.append("\nBest RFP-compliant per architecture (max T/D, then min power):")
    for arch, sub in df[df.rfp_compliant].groupby("architecture"):
        r = sub.sort_values(["T_over_D_air", "P_total_air_W"], ascending=[False, True]).iloc[0]
        out.append(f"  {arch:20s} alt={r.alt_km:.0f} {r.solar:5s} A={r.intake_area_m2:.1f}m2 CR={r.comp_ratio:.0f} "
                   f"mdot={r.mdot_air_mgps:.2f}mg/s p_in={r.p_in_Pa:.2e}Pa  T_air={r.T_air_mN:.1f}mN "
                   f"Isp={r.Isp_air_s:.0f}s P_air={r.P_total_air_W:.0f}W P_peak={r.P_total_peak_W:.0f}W "
                   f"m={r.m_total_kg:.1f}kg Xe={r.xe_total_kg:.1f}kg T/D={r.T_over_D_air:.2f} IC={r.ic_total:.2f}")
    out.append("\nWhy configurations fail (count of failed hard checks):")
    hard = [c for c in df.columns if c.startswith("chk_") and c not in ("chk_hall_preferred", "chk_net_drag_comp_air")]
    fails = {c: int((~df[c]).sum()) for c in hard}
    for c, v in sorted(fails.items(), key=lambda kv: -kv[1]):
        out.append(f"  {c:28s} {v}")
    return "\n".join(out)


def plots(df: pd.DataFrame, outdir: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    outdir.mkdir(parents=True, exist_ok=True)
    # 1) T_air vs P_total by architecture with RFP box
    fig, ax = plt.subplots(figsize=(9, 6))
    for arch, sub in df.groupby("architecture"):
        ax.scatter(sub.P_total_air_W, sub.T_air_mN, s=12, alpha=0.6, label=arch)
    ax.axhspan(12, 25, color="green", alpha=0.08)
    ax.axvline(1500, color="red", ls="--")
    ax.set_xlabel("Total bus power, air mode [W]"); ax.set_ylabel("Thrust on air [mN]")
    ax.set_xlim(0, 2500); ax.set_ylim(0, 40); ax.legend(fontsize=8); ax.set_title("Air-mode thrust vs power (RFP box shaded)")
    fig.savefig(outdir / "thrust_vs_power.png", dpi=140, bbox_inches="tight"); plt.close(fig)
    # 2) T/D vs altitude for feasible configs
    fig, ax = plt.subplots(figsize=(9, 6))
    f = df[df.rfp_compliant]
    for arch, sub in f.groupby("architecture"):
        ax.scatter(sub.alt_km + (hash(arch) % 7 - 3) * 0.8, sub.T_over_D_air, s=14, alpha=0.7, label=arch)
    ax.axhline(1.0, color="red", ls="--"); ax.set_yscale("log")
    ax.set_xlabel("Altitude [km]"); ax.set_ylabel("T_air / D  (feasible configs)"); ax.legend(fontsize=8)
    ax.set_title("Net drag compensation on air alone")
    fig.savefig(outdir / "closure_vs_altitude.png", dpi=140, bbox_inches="tight"); plt.close(fig)
    # 3) mass vs Xe
    fig, ax = plt.subplots(figsize=(9, 6))
    for arch, sub in df.groupby("architecture"):
        ax.scatter(sub.xe_total_kg, sub.m_total_kg, s=12, alpha=0.6, label=arch)
    ax.axhline(40, color="red", ls="--"); ax.set_xlim(0, 30); ax.set_ylim(0, 80)
    ax.set_xlabel("Xe mass over mission [kg]"); ax.set_ylabel("Total propulsion mass [kg]"); ax.legend(fontsize=8)
    fig.savefig(outdir / "mass_vs_xenon.png", dpi=140, bbox_inches="tight"); plt.close(fig)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="abep-sim", description="ABEP system-closure sweep for DTDF/06/13516")
    ap.add_argument("grid", nargs="?", help="YAML grid file (omit for default grid)")
    ap.add_argument("-o", "--out", default="results", help="output directory")
    a = ap.parse_args(argv)
    grid = yaml.safe_load(open(a.grid)) if a.grid else {}
    df = run_grid(grid)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "sweep.csv", index=False)
    s = summarize(df)
    (out / "summary.txt").write_text(s)
    plots(df, out)
    print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
