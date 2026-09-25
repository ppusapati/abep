"""Intake / compressor sizing at 180-200-230 km x solar low/mean/high.

For each case and target sustained air thrust, solve the intake area that delivers the
thrust with the chosen architecture, given a compressor sized to hold the thruster inlet
at p_target = margin * p_min(card). Reports available mg/s per m^2, passive outlet
pressure, required active ratio, compressor power, intake area, drag and T/D.
"""
from __future__ import annotations
import pandas as pd
from .constants import RFP, K_B
from .atmosphere import atmosphere
from .intake import IntakeParams, CompressorParams, collection, passive_compression
from .thruster import CARDS
from .system import Config, evaluate


def _area_for_thrust(arch, alt, solar, T_target_N, accommodation, cr_total, vd, area_ratio):
    lo, hi = 0.05, 30.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        r = evaluate(Config(arch, alt, solar, IntakeParams(area_m2=mid, accommodation=accommodation),
                            CompressorParams(ratio=cr_total, area_ratio=area_ratio), vd_V=vd))
        if r["T_air_mN"] * 1e-3 < T_target_N:
            lo = mid
        else:
            hi = mid
    return hi


def sizing_table(architectures=("hall_1stage", "hall_ecr"), targets_mN=(12.0, 25.0),
                 accommodation=0.5, p_margin=3.0, area_ratio=10.0, vd=None,
                 T_out_K=350.0) -> pd.DataFrame:
    rows = []
    for arch in architectures:
        card = CARDS[arch]
        p_min = card.p_min_Pa if card.stage1 is None else max(card.p_min_Pa, card.stage1.p_min_Pa)
        p_target = p_margin * p_min
        for alt in (180, 200, 230):
            for solar in ("low", "mean", "high"):
                atm = atmosphere(alt, solar)
                col = collection(IntakeParams(area_m2=1.0, accommodation=accommodation), atm)
                comp = CompressorParams(ratio=1.0, area_ratio=area_ratio, T_out_K=T_out_K)
                passive = passive_compression(comp, atm, col["eta_c"])
                p_passive = atm["n"] * passive * K_B * T_out_K
                cr_total = max(p_target / (atm["n"] * K_B * T_out_K), passive)
                for T in targets_mN:
                    A = _area_for_thrust(arch, alt, solar, T * 1e-3, accommodation, cr_total, vd, area_ratio)
                    r = evaluate(Config(arch, alt, solar, IntakeParams(area_m2=A, accommodation=accommodation),
                                        CompressorParams(ratio=cr_total, area_ratio=area_ratio, T_out_K=T_out_K), vd_V=vd))
                    rows.append({
                        "architecture": arch, "alt_km": alt, "solar": solar, "target_T_mN": T,
                        "rho_kg_m3": atm["rho"], "flux_mgps_per_m2": atm["flux_kg_m2_s"] * 1e6,
                        "eta_c": col["eta_c"], "available_mgps_per_m2": col["mdot_collected"] * 1e6,
                        "intake_area_m2": A, "mdot_delivered_mgps": r["mdot_air_mgps"],
                        "passive_ratio": passive, "p_passive_Pa": p_passive,
                        "p_thruster_target_Pa": p_target, "active_ratio_required": r["active_ratio"],
                        "comp_power_W": r["P_comp_W"], "comp_mass_kg": r["m_comp_kg"],
                        "intake_mass_kg": r["m_intake_kg"], "Isp_air_s": r["Isp_air_s"],
                        "P_total_air_W": r["P_total_air_W"], "drag_mN": r["drag_mN"],
                        "T_over_D": r["T_over_D_air"], "m_total_kg": r["m_total_kg"],
                        "O_survival_to_thruster": r["O_survival"], "rfp_compliant": r["rfp_compliant"], "abep_closed": r["abep_closed"],
                        "fails": ",".join(k[4:] for k in r if k.startswith("chk_") and not r[k]
                                          and k not in ("chk_net_drag_comp_air", "chk_hall_preferred",
                                                        "chk_thrust_air_ge_req")),
                    })
    return pd.DataFrame(rows)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="abep-sizing")
    ap.add_argument("-o", "--out", default="results/sizing.csv")
    ap.add_argument("--arch", nargs="+", default=["hall_1stage", "hall_ecr"])
    ap.add_argument("--accommodation", type=float, default=0.5)
    ap.add_argument("--vd", type=float, default=None)
    ap.add_argument("--area-ratio", type=float, default=10.0)
    a = ap.parse_args(argv)
    df = sizing_table(a.arch, accommodation=a.accommodation, vd=a.vd, area_ratio=a.area_ratio)
    from pathlib import Path
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    cols = ["architecture", "alt_km", "solar", "target_T_mN", "available_mgps_per_m2", "intake_area_m2",
            "mdot_delivered_mgps", "passive_ratio", "p_passive_Pa", "active_ratio_required", "comp_power_W",
            "Isp_air_s", "P_total_air_W", "T_over_D", "m_total_kg", "rfp_compliant", "abep_closed", "fails"]
    print(df[cols].round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
