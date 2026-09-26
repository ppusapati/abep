"""Build hallthruster_bridge/propellants/ionization_N2_song2023.dat (e + N2 -> N2+ + 2e, non-dissociative ionization).

Cross section: Song, Cho, Karwasz, Kokoouline & Tennyson, J. Phys. Chem. Ref. Data 52, 023104 (2023),
doi:10.1063/5.0150618, Table 10 ("Recommended total and partial ionization cross sections of N2"), column sigma(N2+),
uncertainty +-5 % (Sec. 2.8). Read from the NSF Public Access Repository copy (https://par.nsf.gov/servlets/purl/10526876,
sha256 f35b73d1f5f11291e6d844cdd8e324f99b6f5b17a9661d2568fca59e9604875d); the PDF is not committed. The recommended set
follows Lindsay & Mangan (Landolt-Bornstein), based on Straub et al. 1996 and, from threshold to 25 eV, Rapp &
Englander-Golden 1965; Itikawa 2006 recommended the same set.

Why the partial column: the reaction produces N2+ only. The total column also counts N+ + N2++ (dissociative and double
ionization, same m/q = 14) and N++; using it here would put those electrons and energy into the wrong channel. Those
channels are not in the current reaction set (a known gap, docs/HISTORY.md 2026-09-26).

Evidence (docs/EVIDENCE.md): level 4 (evaluated literature); quantity type: evaluated measurement, transcribed from a
numeric table (no digitization). Transformation chain:
  measurements (Straub 1996; Rapp & Englander-Golden 1965) -> Lindsay & Mangan evaluation -> JPCRD 2023 Table 10
  -> transcribed here -> Maxwellian integration (abep_sim/rate_tables.py).
Choices, all explicit:
  * sigma = 0 below 16.0 eV (the first tabulated point); no threshold curve constructed from 15.58 eV.
  * Table 10 has no 750 eV row (700 -> 800 eV across the page break; checked in two text extractions). Linear
    interpolation spans it.
  * Above 1000 eV the last value is held ("hold" tail). The tail share of the rate is < 1 % up to 255 eV mean energy.
  * Header energy 15.58 eV = N2 ionization threshold as stated in JPCRD 2023 Sec. 3.
Usage: python scripts/build_n2_ionization_song2023_table.py
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from abep_sim.rate_tables import tail_sensitivity, write_hallthruster_table   # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "hallthruster_bridge", "propellants", "ionization_N2_song2023.dat")
THRESHOLD_EV = 15.58
TAIL = "hold"

# JPCRD 52, 023104 (2023), Table 10: electron energy [eV], sigma(N2+) and sigma(total) [1e-16 cm^2]
TABLE10 = [
    (16.0, 0.0211, 0.0211), (16.5, 0.0466, 0.0466), (17.0, 0.0713, 0.0713), (17.5, 0.0985, 0.0985),
    (18.0, 0.129, 0.129), (18.5, 0.164, 0.164), (19.0, 0.199, 0.199), (19.5, 0.230, 0.230), (20.0, 0.270, 0.270),
    (20.5, 0.308, 0.308), (21.0, 0.344, 0.344), (21.5, 0.380, 0.380), (22.0, 0.418, 0.418), (22.5, 0.455, 0.455),
    (23.0, 0.492, 0.492), (23.5, 0.528, 0.528), (24.0, 0.565, 0.565), (24.5, 0.603, 0.603), (25.0, 0.640, 0.640),
    (30, 0.929, 0.962), (35, 1.16, 1.25), (40, 1.37, 1.54), (45, 1.52, 1.77), (50, 1.60, 1.91), (55, 1.66, 2.05),
    (60, 1.72, 2.16), (65, 1.74, 2.22), (70, 1.78, 2.30), (75, 1.80, 2.36), (80, 1.81, 2.40), (85, 1.82, 2.43),
    (90, 1.83, 2.47), (95, 1.85, 2.50), (100, 1.85, 2.51), (110, 1.83, 2.50), (120, 1.81, 2.48), (140, 1.78, 2.45),
    (160, 1.72, 2.36), (180, 1.67, 2.28), (200, 1.61, 2.19), (225, 1.55, 2.08), (250, 1.48, 1.98), (275, 1.41, 1.89),
    (300, 1.37, 1.82), (350, 1.28, 1.68), (400, 1.20, 1.56), (450, 1.11, 1.45), (500, 1.05, 1.36), (550, 0.998, 1.28),
    (600, 0.943, 1.20), (650, 0.880, 1.12), (700, 0.844, 1.07), (800, 0.765, 0.971), (850, 0.738, 0.936),
    (900, 0.719, 0.907), (950, 0.698, 0.879), (1000, 0.676, 0.847)]


def main():
    E = np.array([r[0] for r in TABLE10], float)
    sig = np.array([r[1] for r in TABLE10], float) * 1e-20      # 1e-16 cm^2 = 1e-20 m^2
    sens = tail_sensitivity(E, sig, [45, 100, 150, 200, 255])
    print(f"Table 10 sigma(N2+): {len(E)} points, {E[0]:.0f}-{E[-1]:.0f} eV, max {sig.max():.3e} m^2 at {E[sig.argmax()]:.0f} eV")
    for eps, d in sens:
        print(f"  tail share at mean energy {eps:5.0f} eV: {100 * d:.4f} %")
    src = ("e + N2 -> N2+ + 2e (non-dissociative). Cross section: Song et al., J. Phys. Chem. Ref. Data 52, 023104 (2023), "
           "Table 10 sigma(N2+) (Lindsay & Mangan evaluation, +-5 %), transcribed; sigma = 0 below 16 eV; held above 1000 eV "
           "(tail share: " + ", ".join(f"{100 * d:.4f} % at {eps:.0f} eV" for eps, d in sens) + "). "
           f"Header {THRESHOLD_EV} eV = N2 ionization threshold (JPCRD 2023 Sec. 3). "
           "Maxwellian-integrated by abep_sim/rate_tables.py (scripts/build_n2_ionization_song2023_table.py). "
           "Energy column = mean electron energy 3/2 Te. Evidence level 4 (docs/EVIDENCE.md). Reaction set abep-n2n-0.2.")
    write_hallthruster_table(OUT, E, sig, THRESHOLD_EV, source=src, tail=TAIL)
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
