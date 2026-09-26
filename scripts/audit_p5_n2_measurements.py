"""P5-N2 measurement audit (before the P5-N2 validation pre-registration; nothing is simulated or scored here).

Source: Brabston, Marino, Lev & Walker, "Hall Thruster Performance and Efficiency Analysis of a Molecular Propellant",
J. Propuls. Power (Article in Advance, 2025), doi:10.2514/1.B39623 (PDF sha256 14db7e8c...; not redistributed). The same paper
supplies the P5-Xe evidence (hallthruster_bridge/identification/brabston_fig8_fig9_xenon.json, docs/EVIDENCE.md).

Tabulated (Table 2, measured): anode N2 flow, cathode Xe flow, V_d, P_d (3 significant figures), peak radial B at the channel
centre / exit plane, chamber pressure (N2-corrected ion gauge at the exit plane). Table 5: maximum diagnostic uncertainties.
Everything else is only in raster figures, digitized here from the embedded images:
  Fig. 5  (p. 9,  xref 469)  thrust vs discharge power, all five N points (ingestion-corrected quantities);
  Fig. 8  (p. 10, xref 56)   component- and thrust-calculated eta_T, N1-N3 (5.0 mg/s only);
  Fig. 9  (p. 11, xref 115)  eta_E, Phi_P, Psi_b, N1-N3;
  Fig. 10 (p. 11, xref 114)  species efficiencies: eta_V,n (E x B), Phi_m,n and eta_SP,n for N2+ and N+, N1-N3.
Axes are calibrated from major ticks (residuals printed); marker centroids by colour after a morphological opening that removes
the connecting lines; triangle markers use their bounding-box centre. The calibration is validated independently: the Fig. 5
xenon markers reproduce the Eq. (14)-corrected Xe powers to <= 0.003 kW, and the Fig. 9/10 N markers fall at V_d = Table 2 to
<= 0.1 V.
Usage: python scripts/audit_p5_n2_measurements.py --pdf <brabston2025.pdf>
Writes hallthruster_bridge/identification/brabston_p5_n2_measurement_audit_v1.json.
"""
import hashlib, json, math, os, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "hallthruster_bridge", "identification", "brabston_p5_n2_measurement_audit_v1.json")
PDF_SHA256 = "14db7e8c1a0e7e4cae472038184a79b88ef4de6cb52071edb2a406d6a52e4d9d"

# Table 2 (N2): anode flow mg/s, cathode Xe mg/s, V_d V, P_d kW, peak radial B G, chamber pressure Torr (N2)
TABLE2 = {"N1": (5.0, 0.44, 231.9, 3.08, 130, 1.47e-5), "N2": (5.0, 0.44, 255.1, 3.69, 130, 1.14e-5),
          "N3": (5.0, 0.44, 278.6, 4.30, 130, 1.19e-5), "N4": (5.2, 0.44, 277.0, 4.56, 130, 1.38e-5),
          "N5": (5.4, 0.44, 275.7, 4.81, 130, 2.14e-5)}
TABLE4_XE = {"Xe1": (230.8, 1.75, 4.49e-5), "Xe2": (250.3, 2.15, 3.94e-5), "Xe3": (274.3, 2.03, 3.28e-5)}
TABLE5_N2 = {"T_mN": 2.6, "Omega": 0.05, "Vp_V": 0.25, "Ib_A": 0.34, "theta_d_deg": 3.3, "Va_n_ExB_V": 11.6}
ABSTRACT_N2_THRUST = {"N1": 61.4, "N5": 90.0}          # "61.4-90.0 mN (nitrogen)": range end-points
MFC_REL = 0.01                                        # "1 % of the current setpoint", max +-0.05 mg/s
A_EN, T0, ZETA_A, ZETA_EN = 0.0488, 300.0, 1.0, 0.8   # Eqs. (13)-(16) as used by the paper
K_B, E_CH, AMU, TORR = 1.380649e-23, 1.602176634e-19, 1.66053906660e-27, 133.322368
M_N2, M_XE = 28.0134 * AMU, 131.293 * AMU


def ingestion(p_torr, m):
    """Eq. (13): entrained mass flow [kg/s] through the 488 cm^2 hemisphere at 300 K."""
    return A_EN * p_torr * TORR * math.sqrt(m / (2 * math.pi * K_B * T0))


def _img(doc, xref):
    import pymupdf
    pix = pymupdf.Pixmap(doc, xref)
    if pix.n - pix.alpha > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3].astype(int)


def _cal(pix, vals):
    c = np.polyfit(pix, vals, 1)
    return c, float(np.abs(np.polyval(c, pix) - np.asarray(vals)).max())


def _blobs(mask, k):
    from scipy import ndimage
    lab, _ = ndimage.label(ndimage.binary_opening(mask, structure=np.ones((k, k))))
    out = []
    for i, s in enumerate(ndimage.find_objects(lab)):
        m = lab[s] == i + 1; yy, xx = np.nonzero(m)
        w, h = s[1].stop - s[1].start, s[0].stop - s[0].start
        out.append(dict(x=xx.mean() + s[1].start, y=yy.mean() + s[0].start, ybox=(s[0].start + s[0].stop - 1) / 2,
                        w=w, h=h, fill=m.sum() / (w * h)))
    return out


def _orange(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (r > 220) & (g > 80) & (g < 150) & (b > 50) & (b < 130)


def digitize(pdf):
    import pymupdf
    doc = pymupdf.open(pdf)
    res, resid = {}, {}
    # Fig. 5: thrust (y, mN) vs power (x, kW); major ticks located on the image (see module docstring)
    a = _img(doc, 469)
    cy, resid["fig5_mN"] = _cal([756.5, 610.5, 466.5, 321.0, 177.0, 33.0], [0, 50, 100, 150, 200, 250])
    cx, resid["fig5_kW"] = _cal([279.5, 521.5, 763.5, 1007, 1248.5, 1492, 1734, 1975.5, 2219.5, 2461], list(np.arange(1.5, 6.01, 0.5)))
    n = sorted([q for q in _blobs(_orange(a), 1) if q["w"] * q["h"] > 200 and q["x"] < 1900], key=lambda q: q["x"])
    assert len(n) == 5, len(n)
    res["fig5"] = {p: {"P_kW": float(np.polyval(cx, q["x"])), "T_mN": float(np.polyval(cy, q["y"]))} for p, q in zip(TABLE2, n)}
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    xe = sorted([q for q in _blobs((r < 60) & (g > 150) & (b > 200), 1) if q["w"] * q["h"] > 200 and q["x"] < 1900], key=lambda q: q["x"])
    res["fig5_xenon_check"] = [{"P_kW": float(np.polyval(cx, q["x"])), "T_mN": float(np.polyval(cy, q["y"]))} for q in xe]
    V = lambda x, l, rr: 225 + (x - l) / (rr - l) * 60        # Figs. 8-10: frame edges are the 225 / 285 V ticks
    # Fig. 9
    a = _img(doc, 115)
    cy, resid["fig9"] = _cal([19, 210, 400, 592, 783, 973, 1164, 1355.5, 1546, 1737], list(np.linspace(1, 0.1, 10)))
    f9 = {}
    for q in _blobs(_orange(a), 9):
        kind = "Psi_b" if q["fill"] > 0.95 else ("eta_E" if q["h"] >= 21 else "Phi_P")
        f9.setdefault(kind, []).append((V(q["x"], 153, 902.5), float(np.polyval(cy, q["ybox"] if kind == "Phi_P" else q["y"]))))
    # upper Psi_b error-bar end: top of the grey bar through each Psi_b marker (Psi_b is the top-most N series)
    grey = (abs(a[..., 0] - a[..., 1]) < 12) & (abs(a[..., 1] - a[..., 2]) < 12) & (a[..., 0] > 60) & (a[..., 0] < 150)
    err = []
    for vd, val in sorted(f9["Psi_b"]):
        xc = 153 + (vd - 225) / 60 * (902.5 - 153)
        rows = np.nonzero(grey[:, int(xc) - 3:int(xc) + 4].any(1))[0]
        y_val = (val - cy[1]) / cy[0]
        above = rows[(rows < y_val) & (rows > y_val - 150)]
        err.append(float(np.polyval(cy, above.min())) - val)
    res["fig9"] = {k: [v for _, v in sorted(vs)] for k, vs in f9.items()}
    res["fig9"]["Psi_b_err_upper"] = err
    res["fig9"]["V_d"] = [v for v, _ in sorted(f9["Psi_b"])]
    # Fig. 8 (N1-N3; markers overlap: the thrust-calculated circle is the upper one)
    a = _img(doc, 56)
    cy, resid["fig8"] = _cal([26.5, 128, 229.5, 332, 433.5, 535, 636.5, 738.5], [.7, .6, .5, .4, .3, .2, .1, 0])
    f8 = sorted([q for q in _blobs(_orange(a), 9) if q["y"] > 300 and q["h"] >= 25], key=lambda q: (q["x"], q["y"]))
    res["fig8"] = {"blobs": [{"V_d": V(q["x"], 229, 2457.5), "y": float(np.polyval(cy, q["y"])), "h_px": int(q["h"])} for q in f8],
                   "note": "N1 and N2 component/thrust markers overlap into one blob; values used only as consistency checks"}
    # Fig. 10
    a = _img(doc, 114)
    cy, resid["fig10"] = _cal([18, 150, 282, 414, 546, 678, 809, 941, 1073, 1205, 1336], list(np.linspace(1, 0, 11)))
    f10 = {}
    for q in _blobs(_orange(a), 9):
        kind = "Phi_m_N2" if q["fill"] > 0.95 else ("eta_V_N2" if q["h"] < 16 else "eta_SP_N2")
        f10.setdefault(kind, []).append((V(q["x"], 136, 753), float(np.polyval(cy, q["ybox"] if kind == "eta_V_N2" else q["y"]))))
    blk = a.sum(2) < 120
    blk[:, :150] = False; blk[:, 740:] = False; blk[:30, :] = False; blk[1170:, :] = False
    black = sorted(_blobs(blk, 11), key=lambda q: q["y"])
    top = [q for q in black if q["y"] < 300]                           # eta_V,N+ triangles (highest series)
    low = sorted([q for q in black if q["y"] >= 300], key=lambda q: (q["x"], q["y"]))
    f10["eta_V_N"] = [(V(q["x"], 136, 753), float(np.polyval(cy, q["ybox"]))) for q in top]
    f10["Phi_m_N"] = [(V(q["x"], 136, 753), float(np.polyval(cy, q["ybox"]))) for q in low if q["w"] < 15]
    f10["eta_SP_N"] = [(V(q["x"], 136, 753), float(np.polyval(cy, q["y"]))) for q in low if q["w"] >= 15]
    res["fig10"] = {k: [v for _, v in sorted(vs)] for k, vs in f10.items()}
    res["fig10"]["V_d"] = [v for v, _ in sorted(f10["eta_V_N2"])]
    res["calibration_max_residual"] = resid
    return res


def main():
    pdf = sys.argv[sys.argv.index("--pdf") + 1]
    assert hashlib.sha256(open(pdf, "rb").read()).hexdigest() == PDF_SHA256, "not the audited PDF"
    d = digitize(pdf)
    pts = {}
    for i, (p, (ma, mc, vd, pd, bg, pr)) in enumerate(TABLE2.items()):
        men = ingestion(pr, M_N2); id_raw = pd * 1e3 / vd; id_corr = id_raw - ZETA_A * men * E_CH / M_N2
        f5 = d["fig5"][p]
        t_corr, t_src = (ABSTRACT_N2_THRUST[p], "abstract range end-point") if p in ABSTRACT_N2_THRUST else (round(f5["T_mN"], 2), "Fig. 5, digitized")
        t_raw = t_corr / (1 - ZETA_EN * men / (ma * 1e-6 + men))
        pts[p] = {"table2": {"mdot_anode_mg_s": ma, "mdot_anode_sigma_mg_s": round(MFC_REL * ma, 3), "mdot_cathode_Xe_mg_s": mc,
                             "V_d": vd, "P_d_kW": pd, "P_d_rounding_kW": 0.005, "B_peak_G": bg, "p_chamber_Torr_N2": pr},
                  "I_d_raw_A": id_raw, "I_d_raw_rounding_rel": 0.005 / pd,
                  "mdot_ingested_eq13_mg_s": men * 1e6, "I_d_corr_eq14_A": id_corr,
                  "T_corr_mN": t_corr, "T_corr_source": t_src, "T_sigma_mN": TABLE5_N2["T_mN"],
                  "T_raw_eq16_inverted_mN": t_raw,
                  "fig5": {"T_mN": f5["T_mN"], "P_kW": f5["P_kW"], "P_eq14_kW": id_corr * vd / 1e3,
                           "P_offset_kW": f5["P_kW"] - id_corr * vd / 1e3}}
        if i < 3:
            k = {"N1": 0, "N2": 1, "N3": 2}[p]
            f9, f10 = d["fig9"], d["fig10"]
            eta_t = (t_corr * 1e-3) ** 2 / (2 * ma * 1e-6 * id_corr * vd)
            comp = f9["eta_E"][k] * f9["Phi_P"][k] * f9["Psi_b"][k]
            psi_b_B = eta_t / (f9["eta_E"][k] * f9["Phi_P"][k])
            pts[p]["fig9"] = {"eta_E": f9["eta_E"][k], "Phi_P": f9["Phi_P"][k], "Psi_b": f9["Psi_b"][k],
                              "Psi_b_err_upper": f9["Psi_b_err_upper"][k]}
            pts[p]["fig10"] = {"eta_V_N2plus": f10["eta_V_N2"][k], "eta_V_Nplus": f10["eta_V_N"][k],
                               "eta_V_sigma": TABLE5_N2["Va_n_ExB_V"] / vd,
                               "Va_N2plus_V": f10["eta_V_N2"][k] * vd, "Va_Nplus_V": f10["eta_V_N"][k] * vd,
                               "Phi_m_N2plus": f10["Phi_m_N2"][k], "Phi_m_Nplus": f10["Phi_m_N"][k],
                               "eta_SP_N2plus": f10["eta_SP_N2"][k], "eta_SP_Nplus": f10["eta_SP_N"][k]}
            pts[p]["consistency"] = {"eta_T_thrust_from_T_Id_corr": eta_t, "eta_T_component_from_fig9": comp,
                                     "Psi_b_implied_reading_B": psi_b_B,
                                     "axial_factor_A": math.sqrt(f9["Psi_b"][k]), "axial_factor_B": math.sqrt(psi_b_B)}
    xe = []
    for (p, (vd, pd, pr)), q in zip(sorted(TABLE4_XE.items(), key=lambda kv: kv[1][1]), sorted(d["fig5_xenon_check"], key=lambda q: q["P_kW"])):
        men = ingestion(pr, M_XE)
        xe.append({"point": p, "P_fig5_kW": q["P_kW"], "P_eq14_kW": (pd * 1e3 / vd - men * E_CH / M_XE) * vd / 1e3})
    out = {"id": "brabston_p5_n2_measurement_audit_v1", "source": "Brabston et al., J. Propuls. Power 2025, doi:10.2514/1.B39623",
           "pdf_sha256": PDF_SHA256, "script": "scripts/audit_p5_n2_measurements.py",
           "calibration_max_residual": d["calibration_max_residual"], "xenon_calibration_check": xe,
           "fig8_raw": d["fig8"], "points": pts}
    json.dump(out, open(OUT, "w"), indent=1)
    for p, v in pts.items():
        print(p, f"Id_raw {v['I_d_raw_A']:.3f} Id_corr {v['I_d_corr_eq14_A']:.3f}  T_corr {v['T_corr_mN']} ({v['T_corr_source']}) fig5 {v['fig5']['T_mN']:.2f}"
              f"  T_raw {v['T_raw_eq16_inverted_mN']:.2f}  P offset {1e3 * v['fig5']['P_offset_kW']:+.1f} W", v.get("consistency", ""))
    print(json.dumps(d["calibration_max_residual"]), xe)


if __name__ == "__main__":
    main()
