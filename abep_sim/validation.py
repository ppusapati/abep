"""Hall-model validation harness (stabilisation gate 3).

Only data that can be cited is loaded. Each record states what was measured, what is derived, and what is uncertain.
The coupled (n_e, T_e) Hall model is calibrated on ONE anchor (Marchioni & Cappelli 2021, N2, 2 mg/s, 250 V); every other
dataset here is a BLIND prediction with that calibration unchanged.

Datasets
--------
CAL  (SUPERSEDED for absolute predictions: the 0-D calibration used an invented 20/35 mm x 100 mm channel; the real ECHT is
     86 mm long, 10 mm wide, 100 mm OD — Marchioni & Cappelli 2021, Sec. 3.)
     Marchioni F., Cappelli M. A., "Extended channel Hall thruster for air-breathing electric propulsion",
     J. Appl. Phys. 130, 053306 (2021). N2, 2 mg/s anode flow, 500-800 W anode power: 17-22 mN, 1000-1100 s, 14-18 %.
     (calibration anchor — not a validation point)

VAL1 Brabston W. P., Marino L. A., Lev D., Walker M. L. R., "Hall Thruster Performance and Efficiency Analysis of a
     Molecular Propellant", J. Propulsion & Power, doi:10.2514/1.B39623 (2025). P5 5-kW HET on pure N2, Table 2 setpoints
     N1-N5: anode flow, discharge voltage, discharge power (-> discharge current exactly), peak radial B 130 G, channel
     length 32 mm (stated). Reported ranges over N1-N5: thrust 61.4-90.0 mN, Isp 1251-1724 s, anode efficiency
     12.8-16.9 %; per-point thrust is only in figures (not transcribed). Stability window on N2: 225-275 V.
     Geometry NOT in the paper: channel radii taken as P5 r_in 61.5 mm / r_out 86.5 mm from memory of the P5 literature
     (Gulczinski 1999; Haas 2001) — MUST be verified before this validation is cited.
"""
from __future__ import annotations
import math
import pandas as pd

G0 = 9.80665

P5_N2 = [  # setpoint, mdot_anode mg/s, Vd V, Pd kW   (Brabston et al. 2025, Table 2)
    ("N1", 5.0, 231.9, 3.08), ("N2", 5.0, 255.1, 3.69), ("N3", 5.0, 278.6, 4.30),
    ("N4", 5.2, 277.0, 4.56), ("N5", 5.4, 275.7, 4.81)]
P5_RANGES = {"T_mN": (61.4, 90.0), "Isp_s": (1251.0, 1724.0), "eta_anode": (0.128, 0.169)}
P5_GEOM = {"r_in_m": 0.0615, "r_out_m": 0.0865, "L_m": 0.032, "B_max_T": 0.013,
           "geometry_provenance": "OD 173 mm, width 25 mm (J. Electric Propulsion 2026, doi 10.1007/s44205-026-00179-9; UM PEPL); L 32 mm (Brabston 2025)"}
ECHT_GEOM = {"r_in_m": 0.040, "r_out_m": 0.050, "L_m": 0.086, "wall": "BN",
             "geometry_provenance": "86 mm long, 10 mm channel height, 100 mm OD (Marchioni & Cappelli 2021, Sec. 3)"}
P5_XE = [  # setpoint, mdot mg/s, Vd V, Pd kW, peak B 162.5 G  (Brabston et al. 2025, Table 4) — conventional-propellant validation
    ("Xe1", 5.0, 230.8, 1.75), ("Xe2", 5.0, 250.3, 2.15), ("Xe3", 5.0, 274.3, 2.03)]
P5_XE_RANGES = {"T_mN": (72.8, 86.8), "Isp_s": (1485.0, 1770.0), "eta_anode": (0.329, 0.396)}


def validate_p5(L_acc_m: float | None = None) -> tuple[pd.DataFrame, dict]:
    from .plasma_devices import coupled_channel, hall_run_coupled
    rows = []
    for sp, md, Vd, Pd_kW in P5_N2:
        ch = coupled_channel(r_in_m=P5_GEOM["r_in_m"], r_out_m=P5_GEOM["r_out_m"], L_m=P5_GEOM["L_m"], B_max_T=P5_GEOM["B_max_T"])
        if L_acc_m is not None:
            ch.L_acc_m = L_acc_m
        r = hall_run_coupled(ch, Vd, {"N2": md * 1e-6})
        Id_meas = Pd_kW * 1e3 / Vd
        T = r["T_N"]
        rows.append({"setpoint": sp, "mdot_mgps": md, "Vd": Vd, "Id_meas_A": Id_meas, "Id_pred_A": r["I_d_A"],
                     "Id_err": r["I_d_A"] / Id_meas - 1.0, "Pd_meas_W": Pd_kW * 1e3, "Pd_pred_W": r["P_d_W"],
                     "T_pred_mN": T * 1e3, "Isp_pred_s": T / (G0 * md * 1e-6),
                     "eta_pred": (T * T / (2 * md * 1e-6 * r["P_d_W"])) if r["P_d_W"] > 0 else 0.0,
                     "Te_pred_eV": r["Te_eV"], "ignited": r.get("ignited", False)})
    df = pd.DataFrame(rows)
    def within(col, key):
        lo, hi = P5_RANGES[key]
        return float(((df[col] >= lo) & (df[col] <= hi)).mean())
    summ = {"dataset": "VAL1 Brabston et al. 2025 (P5, N2)", "n_points": len(df),
            "Id_mean_abs_err": float(df.Id_err.abs().mean()), "Id_max_abs_err": float(df.Id_err.abs().max()),
            "T_pred_range_mN": (float(df.T_pred_mN.min()), float(df.T_pred_mN.max())), "T_meas_range_mN": P5_RANGES["T_mN"],
            "Isp_pred_range_s": (float(df.Isp_pred_s.min()), float(df.Isp_pred_s.max())), "Isp_meas_range_s": P5_RANGES["Isp_s"],
            "eta_pred_range": (float(df.eta_pred.min()), float(df.eta_pred.max())), "eta_meas_range": P5_RANGES["eta_anode"],
            "frac_T_in_range": within("T_pred_mN", "T_mN"), "frac_Isp_in_range": within("Isp_pred_s", "Isp_s"),
            "frac_eta_in_range": within("eta_pred", "eta_anode"), "geometry": P5_GEOM}
    return df, summ


def calibration_anchor() -> dict:
    from .plasma_devices import coupled_channel, hall_run_coupled
    r = hall_run_coupled(coupled_channel(), 250.0, {"N2": 2e-6})
    T = r["T_N"]
    return {"dataset": "CAL Marchioni & Cappelli 2021", "T_mN": T * 1e3, "P_W": r["P_d_W"], "Isp_s": T / (G0 * 2e-6),
            "eta": T * T / (2 * 2e-6 * r["P_d_W"]), "meas": "17-22 mN, 500-800 W, 1000-1100 s, 14-18 %"}


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    print(calibration_anchor())
    df, s = validate_p5(); print(df.round(3).to_string(index=False)); print(s)
