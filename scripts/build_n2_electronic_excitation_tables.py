"""Build the eight N2 electronic-excitation tables excitation_N2_<state>.dat (reaction set abep-n2n-0.9):
X 1Sigma_g+ -> A 3Sigma_u+, B 3Pi_g, W 3Delta_u, B' 3Sigma_u-, a' 1Sigma_u-, a 1Pi_g, w 1Delta_u, C 3Pi_u.

Owner decisions (2026-09-26): eight state-resolved fixed-energy reactions (no lumped reaction); Su et al. 2021 below 20 eV,
Johnson et al. 2005 from 20 eV; the 10-20 eV overlap is used to QUANTIFY disagreement, never to renormalize; no -1.5 eV shift;
energy loss = experimental vertical excitation energies (Oddershede et al., as tabulated in Su 2021 Table 1), not the
calculated R-matrix thresholds.
Sources (committed under hallthruster_bridge/propellants/sources/):
  su2021/*.txt  Su, Cheng, Zhang & Tennyson, J. Phys. B 54, 115203 (2021), CC BY 4.0 supplementary data (cc-pVTZ; Angstrom^2),
                threshold (calculated onsets) to 20 eV. Recommended by Song et al. JPCRD 2023.
  johnson2005_table2_ics.tsv  Johnson, Malone, Kanik, Tran & Khakoo, J. Geophys. Res. 110, A11311 (2005),
                doi:10.1029/2005JA011295, Table 2 integral cross sections (1e-18 cm^2, with uncertainties), 10-100 eV (a 1Pi_g
                also 200 eV). Measured (EEL DCS integrated). Transcribed by the project owner from the Wiley article page (the
                supporting-information file is behind a bot challenge from this environment); values not re-checked here
                against the PDF.
Construction, per state:
  sigma(E) = Su(E) for E < 20 eV; Johnson points for E >= 20 eV (linear in E between them). No smoothing at 20 eV: the step
  there equals the overlap disagreement and is reported (step_at_20()).
  Above Johnson's last point (100 eV; 200 eV for a 1Pi_g): documented continuation sigma = sigma_last (E/E_last)^-p, with p
  from the last two Johnson points (triplets p ~ 2.2-2.9, towards the E^-3 exchange limit; singlets p ~ 0.5-1.7). It is part
  of the declared model; its share of the rate and the zero/hold-tail bounds are reported (continuation_sensitivity()),
  up to 10 keV and zero beyond.
Evidence: level 4. Below 20 eV model-derived (R-matrix theory); 20-100/200 eV measured; above that assumed (continuation).
Usage: python scripts/build_n2_electronic_excitation_tables.py
"""
import os, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from abep_sim.rate_tables import maxwellian_rate, write_hallthruster_table   # noqa: E402

PROP = os.path.join(ROOT, "hallthruster_bridge", "propellants")
SRC = os.path.join(PROP, "sources")
E_JOIN = 20.0
E_CONT_MAX = 1e4
# state key -> (Su file, Johnson column, experimental vertical excitation energy [eV] (Oddershede, Su 2021 Table 1), file tag)
STATES = {"A": ("A3-Sigma_u.txt", "A_3Sigma_u+", 7.75, "A3Sigma_u"),
          "B": ("B3-Pi_g.txt", "B_3Pi_g", 8.04, "B3Pi_g"),
          "W": ("W3-Delta_u.txt", "W_3Delta_u", 8.88, "W3Delta_u"),
          "Bp": ("B'3-Sigma_u.txt", "Bprime_3Sigma_u-", 9.67, "Bprime3Sigma_u"),
          "a": ("a1-Pi_g.txt", "a_1Pi_g", 9.31, "a1Pi_g"),
          "ap": ("a'1-Sigma_u.txt", "aprime_1Sigma_u-", 9.92, "aprime1Sigma_u"),
          "w": ("w1-Delta_u.txt", "w_1Delta_u", 10.27, "w1Delta_u"),
          "C": ("C3-Pi_u.txt", "C_3Pi_u", 11.19, "C3Pi_u")}


def fname(key):
    return f"excitation_N2_{STATES[key][3]}.dat"


def su(key):
    rows = []
    for line in open(os.path.join(SRC, "su2021", STATES[key][0]), encoding="utf-8", errors="replace").read().splitlines()[2:]:
        p = line.split()
        if len(p) >= 2:
            rows.append((float(p[0]), float(p[1]) * 1e-20))          # Angstrom^2 -> m^2
    return np.array([r[0] for r in rows]), np.array([r[1] for r in rows])


def johnson(key):
    col = STATES[key][1]; hdr = None; E, S, U = [], [], []
    for line in open(os.path.join(SRC, "johnson2005_table2_ics.tsv")):
        if line.startswith("#") or not line.strip():
            continue
        p = line.rstrip("\n").split("\t")
        if p[0] == "Energy_eV":
            hdr = p[1:]; continue
        c = p[1 + hdr.index(col)] if 1 + hdr.index(col) < len(p) else ""
        if c.strip():
            v, u = (float(x) for x in c.split("+/-"))
            E.append(float(p[0])); S.append(v * 1e-22); U.append(u * 1e-22)   # 1e-18 cm^2 -> m^2
    return np.array(E), np.array(S), np.array(U)


def slope(key):
    E, S, _ = johnson(key)
    return -np.log(S[-1] / S[-2]) / np.log(E[-1] / E[-2])


def cross_section(key, tail="powerlaw"):
    Es, Ss = su(key); Ej, Sj, _ = johnson(key)
    m = Es < E_JOIN; mj = Ej >= E_JOIN
    E = np.concatenate([Es[m], Ej[mj]]); S = np.concatenate([Ss[m], Sj[mj]])
    if tail == "powerlaw":
        e_last, s_last = E[-1], S[-1]
        Ec = np.geomspace(e_last, E_CONT_MAX, 200)[1:]
        E = np.concatenate([E, Ec]); S = np.concatenate([S, s_last * (Ec / e_last) ** (-slope(key))])
    return E, S


def rate(key, Te, tail="powerlaw"):
    if tail == "powerlaw":
        return maxwellian_rate(*cross_section(key, "powerlaw"), Te, "zero")
    return maxwellian_rate(*cross_section(key, "none"), Te, tail)


def continuation_sensitivity(key, Te):
    """(share of the nominal rate from above Johnson's last point, zero-tail/nominal - 1, hold-tail/nominal - 1)."""
    k = rate(key, Te); kz = rate(key, Te, "zero"); kh = rate(key, Te, "hold")
    return (k - kz) / k, kz / k - 1, kh / k - 1


def step_at_20(key):
    Es, Ss = su(key); Ej, Sj, Uj = johnson(key)
    i = int(np.where(Ej == E_JOIN)[0][0])
    return float(np.interp(E_JOIN, Es, Ss) / Sj[i]), float(Uj[i] / Sj[i])


def overlap(key):
    Es, Ss = su(key); Ej, Sj, Uj = johnson(key)
    return [(float(e), float(np.interp(e, Es, Ss) / s), float(u / s)) for e, s, u in zip(Ej, Sj, Uj) if e <= E_JOIN]


def main():
    for key, (_, col, dE, tag) in STATES.items():
        E, S = cross_section(key)
        st, su_unc = step_at_20(key)
        cs = {Te: continuation_sensitivity(key, Te) for Te in (20, 30)}
        ov = overlap(key)
        src = (f"e + N2(X) -> e + N2({col}). Su et al. J. Phys. B 54, 115203 (2021) (CC BY 4.0) below {E_JOIN:g} eV; Johnson et al. "
               f"J. Geophys. Res. 110, A11311 (2005) Table 2 from {E_JOIN:g} eV; power-law continuation p = {slope(key):.2f} above "
               "Johnson's last point (to 10 keV). Overlap Su/Johnson: " + ", ".join(f"{e:g} eV {r:.2f} (+-{u:.2f})" for e, r, u in ov)
               + f"; step at 20 eV Su/Johnson = {st:.2f}. Continuation share of the rate: "
               + ", ".join(f"T_e {T} eV {100 * v[0]:.1f} % (zero/hold tail {100 * v[1]:+.1f}/{100 * v[2]:+.1f} %)" for T, v in cs.items())
               + f". Header {dE} eV = experimental vertical excitation energy (Oddershede, Su 2021 Table 1); no threshold shift. "
               "Maxwellian-integrated by abep_sim/rate_tables.py (scripts/build_n2_electronic_excitation_tables.py). Reaction set abep-n2n-0.9.")
        write_hallthruster_table(os.path.join(PROP, fname(key)), E, S, dE, source=src, tail="zero", header_label="Excitation energy")
        print(f"{fname(key):32s} dE {dE:5.2f}  p {slope(key):.2f}  step@20 {st:.2f}  cont@30 {100 * cs[30][0]:.1f} % "
              f"(zero {100 * cs[30][1]:+.1f} / hold {100 * cs[30][2]:+.1f} %)")


if __name__ == "__main__":
    main()
