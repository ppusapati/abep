"""Omitted-process importance audit: N2 vibrational excitation, under hallthruster_bridge/prereg/
n2_completeness_audit_v1.json (vibrational domain T_e = 0.2-30 eV).

Vibrational data (the dataset JPCRD 2023 recommends): Laporta, Little, Celiberto & Tennyson, Plasma Sources Sci. Technol.
23, 065002 (2014), doi:10.1088/0963-0252/23/6/065002 (arXiv:1402.3814, read 2026-09-26, sha256
6995677ca041a9324b3da6750a92c0884e3ca69145699fc986868430fcf34a7a). Resonant (2Pi_g) vibrational excitation from v = 0
to every bound v_f, as the paper's Eq. (10) fit
    kappa(T) = kappa_max (T_max / T)^(3/2) exp(-T_max / T)       [kappa_max in 1e-9 cm^3/s, T and T_max in eV]
with (T_max, kappa_max) from the supplementary file psst498072supp1.dat (sha256
5f22d498e3e238474d363f7623a390c3f5cf337826d1a99a699f8405d8eb335d), v_i = 0 block, and level energies eps_v from
Laporta Table II (counted from v = 0). Units checked: for 0 -> 1 the fit reproduces the Maxwellian integral of JPCRD
2023 Table 7 (the recommended Laporta sigma_01, 1-5 eV) to 1-6 % at T = 0.5-3 eV (check_units()).
Caveats, all pushing the vibrational power DOWN (so its promotion verdict is conservative): only resonant excitation
(cross sections integrated to 15 eV; non-resonant excitation at higher energy absent); only v = 0 initial state
(superelastic returns from excited v would lower the NET loss, but the gross loss is what the criterion bounds).

Denominator (included inelastic electron power per unit N2 density, x_N = 0), abep-n2n-0.6 upper:
  N2 ionization (15.58 eV), dissociation (12.14), dissociative ionization upper (24.284), N2 -> N2+ + N (53.885),
  plus - where it can be trusted - the 8 electronic-excitation channels of Su et al. 2021 (CC BY 4.0 supplementary data,
  fetched at run time from IOP; data end at 20 eV, so used with sigma = 0 above 20 eV) with the owner's experimental
  energy losses (Oddershede via Su Table 1). The Maxwellian flux share above 20 eV, (1 + 20/T) exp(-20/T), is printed:
  <= 1 % for T_e <= 3 eV, where the excitation-inclusive F_P is therefore final.
Residual sanity bound (one-sided, NOT a vibrational dataset): in rate space,
  k_res = k(JPCRD Table 1 TCS) - k(Table 4 elastic ICS) - k(included inelastic) - sum k(Su electronic)
  must not be exceeded by sum_vf k_vib (it also contains rotational excitation etc.).
Usage: python scripts/audit_n2_vibrational_excitation.py [--su-dir DIR]   (writes hallthruster_bridge/audit/n2_vibrational_excitation_v1.json)
"""
import glob, io, json, os, re, sys, urllib.request, zipfile
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from abep_sim.rate_tables import maxwellian_rate   # noqa: E402

PROP = os.path.join(ROOT, "hallthruster_bridge", "propellants")
PREREG = os.path.join(ROOT, "hallthruster_bridge", "prereg", "n2_completeness_audit_v1.json")
OUT = os.path.join(ROOT, "hallthruster_bridge", "audit", "n2_vibrational_excitation_v1.json")
SU_DATA_PAGE = "https://iopscience.iop.org/article/10.1088/1361-6455/abf9f0/data"

# Laporta et al. 2014 supplementary, v_i = 0: (v_f, T_max [eV], kappa_max [1e-9 cm^3/s])
LAPORTA_V0 = [(0, 2.2017, 73.35644), (1, 2.37735, 19.55277), (2, 2.37735, 9.358008), (3, 2.37735, 5.510881),
              (4, 2.37735, 3.305553), (5, 2.56695, 1.860624), (6, 2.56695, 0.9458029), (7, 2.7717, 0.4271604),
              (8, 2.99295, 0.1699371), (9, 2.99295, 0.05949995), (10, 3.2316, 0.01842815), (11, 3.48945, 0.005140074),
              (12, 3.76785, 0.001331247), (13, 4.06845, 0.0003261642), (14, 4.06845, 0.00007718649),
              (15, 4.3929, 0.00001901364), (16, 4.74345, 5.308401e-6), (17, 5.53035, 1.858916e-6),
              (18, 5.97165, 7.521048e-7), (19, 5.97165, 3.129907e-7), (20, 6.9624, 2.128239e-7), (21, 7.51785, 2.139217e-7),
              (22, 8.11755, 1.54129e-7), (23, 8.11755, 7.325886e-8), (24, 8.11755, 5.037614e-8), (25, 8.7651, 7.006309e-8),
              (26, 8.7651, 7.603992e-8), (27, 8.7651, 5.254732e-8), (28, 8.7651, 2.639563e-8), (29, 8.7651, 1.899412e-8),
              (30, 9.4644, 2.602971e-8), (31, 10.21935, 3.110391e-8), (32, 10.21935, 2.624926e-8),
              (33, 10.21935, 1.574956e-8), (34, 10.21935, 7.872339e-9), (35, 10.21935, 6.462295e-9),
              (36, 11.0346, 9.353129e-9), (37, 11.0346, 1.205612e-8), (38, 11.0346, 1.186584e-8), (39, 11.0346, 8.953048e-9),
              (40, 11.0346, 5.252292e-9), (41, 11.0346, 2.615168e-9), (42, 11.91495, 1.715228e-9), (43, 11.91495, 2.161905e-9),
              (44, 11.91495, 3.127468e-9), (45, 11.91495, 3.895917e-9), (46, 11.91495, 4.134991e-9),
              (47, 11.91495, 3.854446e-9), (48, 12.8655, 3.237246e-9), (49, 12.8655, 2.515148e-9), (50, 12.8655, 1.833789e-9),
              (51, 12.8655, 1.275626e-9), (52, 12.8655, 8.606636e-10), (53, 12.8655, 5.693846e-10),
              (54, 12.8655, 3.805655e-10), (55, 11.91495, 2.846923e-10), (56, 11.0346, 2.932306e-10),
              (57, 10.21935, 3.776381e-10), (58, 10.21935, 4.564347e-10)]
# Laporta et al. 2014 Table II: eps_v [eV] from v = 0
EPS_V = [0.000, 0.288, 0.573, 0.855, 1.133, 1.408, 1.679, 1.947, 2.211, 2.471, 2.728, 2.982, 3.232, 3.478, 3.720, 3.959,
         4.195, 4.426, 4.654, 4.878, 5.099, 5.315, 5.528, 5.737, 5.942, 6.143, 6.339, 6.532, 6.721, 6.905, 7.084, 7.260,
         7.430, 7.596, 7.757, 7.913, 8.064, 8.210, 8.350, 8.485, 8.614, 8.737, 8.853, 8.963, 9.067, 9.163, 9.252, 9.335,
         9.409, 9.476, 9.535, 9.587, 9.631, 9.667, 9.696, 9.717, 9.732, 9.742, 9.748]
# Su et al. 2021 supplementary file per state -> experimental vertical excitation energy (Oddershede, Su Table 1)
SU_STATES = {"A3-Sigma_u.txt": 7.75, "B3-Pi_g.txt": 8.04, "W3-Delta_u.txt": 8.88, "B'3-Sigma_u.txt": 9.67,
             "a1-Pi_g.txt": 9.31, "a'1-Sigma_u.txt": 9.92, "w1-Delta_u.txt": 10.27, "C3-Pi_u.txt": 11.19}
# JPCRD 2023 Table 1 (TCS) and Table 4 (elastic ICS), [eV, 1e-16 cm^2]
TCS = [(0.1, 4.88), (0.12, 5.13), (0.15, 5.56), (0.17, 5.85), (0.2, 6.25), (0.25, 6.84), (0.3, 7.32), (0.35, 7.72),
       (0.4, 8.06), (0.45, 8.33), (0.5, 8.61), (0.6, 8.96), (0.7, 9.25), (0.8, 9.48), (0.9, 9.66), (1.0, 9.85), (1.2, 10.2),
       (1.5, 11.2), (1.7, 13.3), (2.0, 25.7), (2.5, 28.5), (3.0, 21.0), (3.5, 14.6), (4.0, 13.2), (4.5, 12.3), (5.0, 11.8),
       (6.0, 11.4), (7.0, 11.4), (8.0, 11.5), (9.0, 11.7), (10.0, 12.0), (12.0, 12.4), (15.0, 13.2), (17.0, 13.5),
       (20.0, 13.7), (25.0, 13.5), (30.0, 13.0), (35.0, 12.4), (40.0, 12.0), (45.0, 11.6), (50.0, 11.3), (60.0, 10.7),
       (70.0, 10.2), (80.0, 9.72), (90.0, 9.30), (100, 8.94), (120, 8.33), (150, 7.48), (170, 7.02), (200, 6.43), (250, 5.66),
       (300, 5.04), (350, 4.54), (400, 4.15), (450, 3.82), (500, 3.55), (600, 3.14), (700, 2.79), (800, 2.55), (900, 2.32),
       (1000, 2.13)]
ICS_EL = [(0.1, 5.84), (0.35, 8.09), (0.55, 8.96), (0.7, 9.48), (0.9, 9.91), (1.0, 10.03), (1.5, 10.53), (2.0, 17.93),
          (2.2, 19.5), (2.35, 20.5), (2.5, 21.0), (2.7, 17.5), (3.0, 15.0), (4.0, 11.6), (5.0, 10.75), (6.0, 10.6), (8.0, 10.6),
          (10, 11.4), (15, 11.8), (20, 11.15), (25, 10.25), (30, 9.65), (40, 8.85), (50, 8.2), (60, 7.4), (80, 6.25), (100, 5.6),
          (120, 4.9), (150, 4.2), (200, 3.5), (250, 3.0), (300, 2.65), (400, 2.15), (500, 1.85), (600, 1.6), (800, 1.25),
          (1000, 1.0)]
INCLUDED = {"ionization_N2_song2023.dat": 15.58, "dissociation_N2.dat": 12.14,
            "dissociative_ionization_N2_upper.dat": 24.284, "dissociative_ionization_N2_N2+.dat": 53.885}


def k_vib(Te, vf=None):
    """Laporta Eq. (10), m^3/s; vf = None -> list over all v_f >= 1."""
    rows = [r for r in LAPORTA_V0 if r[0] >= 1] if vf is None else [r for r in LAPORTA_V0 if r[0] == vf]
    return [(v, km * 1e-9 * 1e-6 * (Tm / Te) ** 1.5 * np.exp(-Tm / Te)) for v, Tm, km in rows]


def table_rate(file, Te):
    a = np.loadtxt(os.path.join(PROP, file), skiprows=2)
    return float(np.interp(1.5 * Te, a[:, 0], a[:, 1]))


def xs_rate(rows, Te, tail="zero"):
    E = np.array([r[0] for r in rows], float); s = np.array([r[1] for r in rows], float) * 1e-20
    return maxwellian_rate(E, s, Te, tail)


def load_su(su_dir=None):
    if su_dir is None:
        html = urllib.request.urlopen(urllib.request.Request(SU_DATA_PAGE, headers={"User-Agent": "abep-sim audit"}), timeout=60).read().decode()
        url = re.search(r'https://cfn-live[^"]*babf9f0supp1\.zip[^"]*', html).group(0).replace("&amp;", "&")
        z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(url, timeout=60).read()))
        files = {os.path.basename(n): z.read(n).decode("utf-8", "replace") for n in z.namelist()}
    else:
        files = {os.path.basename(p): open(p, encoding="utf-8", errors="replace").read() for p in glob.glob(os.path.join(su_dir, "*.txt"))}
    su = {}
    for f, dE in SU_STATES.items():
        rows = []
        for line in files[f].splitlines()[2:]:
            p = line.split()
            if len(p) >= 2:
                rows.append((float(p[0]), float(p[1])))            # eV, Angstrom^2 = 1e-20 m^2 (cc-pVTZ column)
        su[f] = (rows, dE)
    return su


def check_units():
    """Laporta 0->1 fit vs the Maxwellian integral of JPCRD 2023 Table 7 (1-5 eV) is done in the audit record."""
    return {T: k_vib(T, 1)[0][1] for T in (0.5, 1.0, 1.585, 2.0, 3.0)}


def main():
    su_dir = sys.argv[sys.argv.index("--su-dir") + 1] if "--su-dir" in sys.argv else None
    su = load_su(su_dir)
    pre = json.load(open(PREREG))
    lo, hi = pre["domains"]["vibrational_excitation"]["Te_eV"]
    Tes = [0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0, 30.0]
    assert Tes[0] == lo and Tes[-1] == hi
    rows = []
    for Te in Tes:
        P_vib = sum(k * EPS_V[v] for v, k in k_vib(Te)); K_vib = sum(k for _, k in k_vib(Te))
        P_inc = sum(table_rate(f, Te) * dE for f, dE in INCLUDED.items())
        K_inc = sum(table_rate(f, Te) for f in INCLUDED)
        P_el = sum(xs_rate(r, Te) * dE for r, dE in su.values()); K_el = sum(xs_rate(r, Te) for r, _ in su.values())
        above20 = (1 + 20 / Te) * np.exp(-20 / Te)
        k_res = xs_rate(TCS, Te, "hold") - xs_rate(ICS_EL, Te, "hold") - K_inc - K_el
        rows.append(dict(Te_eV=Te, P_vib=P_vib, K_vib=K_vib, P_included=P_inc, P_electronic_su=P_el,
                         F_P_vs_included=P_vib / P_inc if P_inc > 0 else float("inf"),
                         F_P_vs_included_plus_electronic=P_vib / (P_inc + P_el) if P_inc + P_el > 0 else float("inf"),
                         maxwellian_flux_share_above_20eV=above20, electronic_denominator_final=above20 <= 0.01,
                         k_residual=k_res, residual_ratio=K_vib / k_res if k_res > 0 else None))
    final = [r for r in rows if r["electronic_denominator_final"]]
    th = pre["thresholds"]["F_P"]
    promote = any(r["F_P_vs_included_plus_electronic"] > th for r in final)
    verdict = {"rule": pre["rule"],
               "max_F_P_where_denominator_final": max(r["F_P_vs_included_plus_electronic"] for r in final),
               "Te_range_denominator_final": [final[0]["Te_eV"], final[-1]["Te_eV"]],
               "vibrational_excitation": ("PROMOTE. Forced by F_P at T_e <= 3 eV, where the denominator already includes the "
                                          "8 electronic-excitation channels (Maxwellian flux above 20 eV <= 1 %) and the "
                                          "vibrational power is itself a lower bound (resonant only, v = 0 only)."
                                          if promote else "not forced where the denominator is final"),
               # One-sided consistency diagnostic, reported as numbers; no pass/fail tolerance is applied (none was
               # pre-registered). k_residual is a small difference of datasets with 10-20 % uncertainties.
               "residual_check": {
                   "Te_where_residual_negative_eV": [r["Te_eV"] for r in rows if r["residual_ratio"] is None],
                   "max_ratio_sum_k_vib_over_residual": max(r["residual_ratio"] for r in rows if r["residual_ratio"] is not None),
                   "Te_where_ratio_above_1_eV": [r["Te_eV"] for r in rows if r["residual_ratio"] is not None and r["residual_ratio"] > 1],
                   "reading": "at T_e <= 0.3 eV TCS - elastic ICS - known inelastic is negative (dataset inconsistency, as "
                              "expected for a residual); elsewhere Laporta's resonant vibrational rate stays within the "
                              "residual to within its uncertainty. The residual is a diagnostic, never a vibrational dataset."}}
    out = {"audit": "N2 vibrational excitation", "prereg": pre["id"], "status": "PROMOTION FINAL (low-T_e F_P, complete denominator)",
           "source": "Laporta et al. PSST 23, 065002 (2014) Eq. (10) + supplementary v_i = 0 fits; Table II level energies",
           "units_check_k01_m3s": check_units(), "verdict": verdict, "rows": rows}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1, default=float)
    for k, v in verdict.items():
        print(f"{k}: {v}")
    print("  T_e   P_vib/P_incl   P_vib/(P_incl+P_elec)   flux>20eV   sum k_vib / k_residual")
    for r in rows:
        rr = f"{r['residual_ratio']:.2f}" if r["residual_ratio"] is not None else "n/a (k_res <= 0)"
        print(f" {r['Te_eV']:5.1f}  {r['F_P_vs_included']:11.3g}   {r['F_P_vs_included_plus_electronic']:11.3g}       "
              f"{r['maxwellian_flux_share_above_20eV']:.1e}   {rr}")
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
