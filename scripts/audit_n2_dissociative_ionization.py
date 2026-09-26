"""Omitted-process importance audit: N2 dissociative ionization (DI), under hallthruster_bridge/prereg/
n2_completeness_audit_v1.json (pre-registered 2026-09-26, before any P5-N2 scoring). PROVISIONAL: the denominators use
reaction set abep-n2n-0.3 (N2 ionization, N2 dissociation, N ionization), which still lacks the 8 electronic-excitation
and the vibrational channels; the audit must be repeated once those exist.

Omitted process, bounded from JPCRD 52, 023104 (2023) Table 10 (Song et al.), column sigma(N+ + N2++):
  e + N2 -> N+ + N + 2e (single DI, Eq. 7), mixed in mass spectrometry with N2++ (about 1 % of total ionization) and
  N+ + N+ (Eq. 8). The whole column is therefore an UPPER bound on single DI. Column sigma(N++) (N2 -> N++ + ...) is
  audited alongside as multiply-ionizing DI.
Near threshold the column starts at 30 eV, but the thermochemical threshold is lower:
  E_th(N+ + N) = D0(N2) + IE(N) = 9.75 (JPCRD Eq. 4) + 14.534 (NIST, ionization_N.dat) = 24.284 eV.
  Two cross-section variants bracket the rate: "table" (sigma = 0 below 30 eV, as published) and "envelope" (sigma held
  at its 30 eV value from 24.284 eV: an over-estimate, not a threshold shape).
Energy loss per DI event: from E_th (lower) to E_th + 2 x 8 eV (upper; 8 eV is the largest N+ kinetic-energy peak reported
  in JPCRD Sec. 2.8 (Crowe & McConkey), equal-mass fragments give KER = 2 KE_ion).
Ions per event: the column is an ion-production cross section (nu = 1); nu = 2 bounds N+ + N+ events.
Denominators (abep-n2n-0.3, per unit N2 density, atomic-N fraction x = n_N/n_N2):
  P_e = k_iz,N2 * 15.58 + k_diss * 12.14 + x * k_iz,N * 14.534        (inelastic; elastic recoil excluded)
  ion production = k_iz,N2 + x * k_iz,N
  x = 0 maximises F_P and F_ion (N only adds to the denominators); it is used for the verdict.
Species-specific (F_S_s > 5 %):
  N+ production: the only modeled N+ source is N + e -> N+ + 2e, so F_S(N+) = k_DI / (k_DI + x k_iz,N); it is reported as
  the atomic fraction x_crit above which F_S(N+) would drop below 5 %.
  N2 destruction: k_DI / (k_iz,N2 + k_diss). N production: k_DI / (k_DI + 2 k_diss).
Fractions use the literal pre-registered form (omitted over the included sum), the conservative variant.
Usage: python scripts/audit_n2_dissociative_ionization.py   (writes hallthruster_bridge/audit/n2_dissociative_ionization_v1.json)
"""
import json, os, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from abep_sim.rate_tables import maxwellian_rate   # noqa: E402

PROP = os.path.join(ROOT, "hallthruster_bridge", "propellants")
PREREG = os.path.join(ROOT, "hallthruster_bridge", "prereg", "n2_completeness_audit_v1.json")
OUT = os.path.join(ROOT, "hallthruster_bridge", "audit", "n2_dissociative_ionization_v1.json")

E_TH_DI = 9.75 + 14.534
KER_MAX_EV = 2 * 8.0
DE = {"ionization_N2_song2023.dat": 15.58, "dissociation_N2.dat": 12.14, "ionization_N.dat": 14.534}

# JPCRD 52, 023104 (2023), Table 10: energy [eV], sigma(N+ + N2++), sigma(N++) [1e-16 cm^2] (blank cells omitted)
TABLE10_NPLUS = [(30, 0.0325), (35, 0.0904), (40, 0.166), (45, 0.245), (50, 0.319), (55, 0.39), (60, 0.438), (65, 0.482),
                 (70, 0.523), (75, 0.561), (80, 0.587), (85, 0.605), (90, 0.632), (95, 0.645), (100, 0.656), (110, 0.66),
                 (120, 0.661), (140, 0.652), (160, 0.633), (180, 0.595), (200, 0.566), (225, 0.516), (250, 0.493),
                 (275, 0.458), (300, 0.438), (350, 0.393), (400, 0.351), (450, 0.324), (500, 0.299), (550, 0.274),
                 (600, 0.248), (650, 0.234), (700, 0.217), (800, 0.2), (850, 0.192), (900, 0.183), (950, 0.176),
                 (1000, 0.167)]
TABLE10_NPP = [(70, 0.00171), (75, 0.00658), (80, 0.0122), (85, 0.0204), (90, 0.0328), (95, 0.0439), (100, 0.0495),
               (110, 0.0725), (120, 0.0927), (140, 0.122), (160, 0.137), (180, 0.154), (200, 0.154), (225, 0.154),
               (250, 0.142), (275, 0.141), (300, 0.128), (350, 0.117), (400, 0.103), (450, 0.094), (500, 0.0808),
               (550, 0.0796), (600, 0.076), (650, 0.0701), (700, 0.0649), (800, 0.0594), (850, 0.0543), (900, 0.0522),
               (950, 0.0505), (1000, 0.0485)]


def table_rate(file, Te):
    a = np.loadtxt(os.path.join(PROP, file), skiprows=2)
    return float(np.interp(1.5 * Te, a[:, 0], a[:, 1]))


def omitted_rate(rows, Te, envelope_from=None):
    E = np.array([r[0] for r in rows], float); s = np.array([r[1] for r in rows], float) * 1e-20
    if envelope_from is not None:
        E, s = np.concatenate([[envelope_from], E]), np.concatenate([[s[0]], s])
    return maxwellian_rate(E, s, Te, "hold")


def main():
    pre = json.load(open(PREREG))
    lo, hi = pre["domains"]["default"]["Te_eV"]
    th = pre["thresholds"]
    Tes = np.round(np.arange(lo, hi + 1e-9, 0.5), 3)
    rows = []
    for Te in Tes:
        k_iz = table_rate("ionization_N2_song2023.dat", Te); k_d = table_rate("dissociation_N2.dat", Te)
        k_N = table_rate("ionization_N.dat", Te)
        k_tab = omitted_rate(TABLE10_NPLUS, Te); k_env = omitted_rate(TABLE10_NPLUS, Te, envelope_from=E_TH_DI)
        k_pp = omitted_rate(TABLE10_NPP, Te)
        P = k_iz * DE["ionization_N2_song2023.dat"] + k_d * DE["dissociation_N2.dat"]
        r = dict(Te_eV=float(Te), k_iz_N2=k_iz, k_diss=k_d, k_iz_N=k_N, k_DI_table=k_tab, k_DI_envelope=k_env, k_Npp=k_pp,
                 F_P_lower=k_tab * E_TH_DI / P, F_P_upper=k_env * (E_TH_DI + KER_MAX_EV) / P,
                 F_ion_lower=k_tab / k_iz, F_ion_upper=2 * k_env / k_iz,
                 F_S_N2_destruction_upper=k_env / (k_iz + k_d), F_S_N_production_upper=k_env / (k_env + 2 * k_d),
                 x_crit_Nplus_lower=19 * k_tab / k_N if k_N > 0 else None,
                 x_crit_Nplus_upper=19 * k_env / k_N if k_N > 0 else None,
                 F_ion_Npp_upper=2 * k_pp / k_iz)
        rows.append(r)
    first = lambda key, t: next((r["Te_eV"] for r in rows if r[key] > t), None)
    verdict = {
        "F_P_max_lower": max(r["F_P_lower"] for r in rows), "F_P_max_upper": max(r["F_P_upper"] for r in rows),
        "F_ion_max_lower": max(r["F_ion_lower"] for r in rows), "F_ion_max_upper": max(r["F_ion_upper"] for r in rows),
        "Te_first_F_P_lower_above_threshold": first("F_P_lower", th["F_P"]),
        "Te_first_F_ion_lower_above_threshold": first("F_ion_lower", th["F_ion"]),
        "F_S_N2_destruction_max_upper": max(r["F_S_N2_destruction_upper"] for r in rows),
        "F_S_N_production_max_upper": max(r["F_S_N_production_upper"] for r in rows),
        "F_ion_Npp_max_upper": max(r["F_ion_Npp_upper"] for r in rows),
    }
    promote = verdict["F_P_max_lower"] > th["F_P"] or verdict["F_ion_max_lower"] > th["F_ion"]
    verdict["rule"] = pre["rule"]
    verdict["dissociative_ionization"] = ("PROMOTE (even the lower bound exceeds the pre-registered threshold)" if promote
                                          else "not decided by the lower bound; see upper bounds")
    out = {"audit": "N2 dissociative ionization", "prereg": pre["id"], "status": "PROVISIONAL",
           "denominator_reaction_set": "abep-n2n-0.3 without the 8 excitation and vibrational channels (inelastic denominator too small -> F_P over-estimated; F_ion unaffected)",
           "E_th_DI_eV": E_TH_DI, "KER_max_eV": KER_MAX_EV, "atomic_fraction_x": 0.0,
           "source": "Song et al. JPCRD 52, 023104 (2023) Table 10, columns sigma(N+ + N2++) and sigma(N++)",
           "verdict": verdict, "rows": rows}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)
    for k, v in verdict.items():
        print(f"{k}: {v}")
    print(" Te  F_P[lo,up]      F_ion[lo,up]    F_S(N2 destr)up  x_crit(N+)[lo,up]")
    for r in rows:
        if r["Te_eV"] in (2, 3, 5, 7.5, 10, 15, 20, 25, 30):
            print(f"{r['Te_eV']:4.1f} {r['F_P_lower']:.4f} {r['F_P_upper']:.4f}  {r['F_ion_lower']:.4f} {r['F_ion_upper']:.4f}  "
                  f"{r['F_S_N2_destruction_upper']:.4f}  {r['x_crit_Nplus_lower']:.3g} {r['x_crit_Nplus_upper']:.3g}")
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
