"""Build hallthruster_bridge/propellants/elastic_N2_song2023.dat (e + N2 elastic momentum transfer).

Cross section: Song, Cho, Karwasz, Kokoouline & Tennyson, J. Phys. Chem. Ref. Data 52, 023104 (2023),
doi:10.1063/5.0150618, Table 5 ("Recommended elastic MTCS of N2"), 0.001 eV - 10 keV. Read from the NSF Public Access
Repository copy (https://par.nsf.gov/servlets/purl/10526876, sha256
f35b73d1f5f11291e6d844cdd8e324f99b6f5b17a9661d2568fca59e9604875d); the PDF is not committed. The recommended values are
those of Kawaguchi et al. (JPCRD ref. 28), who gave no uncertainties; Song et al. estimate "of the order of a few percent"
for most energies (Sec. 2.3). Table 5 is a subsample ("a more complete dataset can be obtained directly from Ref. 28").

Why momentum transfer: HallThruster.jl uses the elastic rate as the electron-neutral momentum-transfer collision
frequency, so the momentum-transfer cross section (not the integral elastic cross section) is the right input.

Evidence (docs/EVIDENCE.md): level 4 (evaluated literature); quantity type: evaluated (measurement + theory), transcribed
from a numeric table (no digitization). Transformation chain:
  beam + swarm measurements and calculations -> Kawaguchi et al. evaluation -> JPCRD 2023 Table 5 (40 points)
  -> transcribed here -> linear interpolation in E -> Maxwellian integration (abep_sim/rate_tables.py).
Choices, all explicit:
  * Linear interpolation in E between the tabulated points, as for every other table. Table 5 is sparse where the Hall
    discharge lives (4.0, 10.9, 21.9, 30.7 eV); the script prints the rate difference against log-log interpolation as a
    transformation uncertainty. The table is not densified or reshaped.
  * sigma = 0 below 0.001 eV; held above 10 keV (tail share is nil on the 0-255 eV grid).
  * Only elastic momentum transfer: rotational/vibrational excitation are not in the reaction set (a known gap).
  * Header energy 0 (no inelastic loss); HallThruster.jl reads the number after the colon only.
Usage: python scripts/build_n2_elastic_song2023_table.py
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from abep_sim.rate_tables import maxwellian_rate, tail_sensitivity, write_hallthruster_table   # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "hallthruster_bridge", "propellants", "elastic_N2_song2023.dat")
TAIL = "hold"

# JPCRD 52, 023104 (2023), Table 5: electron energy [eV], elastic MTCS [1e-16 cm^2]
TABLE5 = [(0.001, 1.36), (0.02, 2.85), (0.03, 3.4), (0.04, 3.85), (0.05, 4.33), (0.1, 5.95), (0.2, 7.9), (0.3, 9.0),
          (0.4, 9.59), (0.5, 9.8), (0.6, 9.87), (0.7, 9.95), (0.8, 10.0), (0.9, 10.0), (1.0, 10.0), (2.02, 17.3),
          (3.0, 14.0), (4.0, 10.5), (10.9, 9.72), (21.9, 6.33), (30.7, 5.21), (50.4, 3.55), (72.5, 2.42), (84.7, 1.89),
          (100, 1.54), (150, 1.01), (202, 0.665), (303, 0.407), (398, 0.305), (471, 0.245), (579, 0.181), (713, 0.139),
          (867, 0.105), (1000, 0.085), (1995, 0.032), (3020, 0.017), (4074, 0.011), (5495, 0.007), (7762, 0.004),
          (10000, 0.003)]


def loglog_dense(E, sig, n=20000):
    """Same points, log-log interpolation, sampled densely (diagnostic only)."""
    x = np.geomspace(E[0], E[-1], n)
    return x, np.exp(np.interp(np.log(x), np.log(E), np.log(sig)))


def interpolation_sensitivity(E, sig, eps_values):
    xd, sd = loglog_dense(E, sig)
    return [(float(eps), maxwellian_rate(xd, sd, eps / 1.5, TAIL) / maxwellian_rate(E, sig, eps / 1.5, TAIL) - 1)
            for eps in eps_values]


def main():
    E = np.array([r[0] for r in TABLE5], float)
    sig = np.array([r[1] for r in TABLE5], float) * 1e-20      # 1e-16 cm^2 = 1e-20 m^2
    sens = tail_sensitivity(E, sig, [45, 150, 255])
    interp = interpolation_sensitivity(E, sig, [3, 15, 30, 45, 90, 255])
    print(f"Table 5 MTCS: {len(E)} points, {E[0]}-{E[-1]:.0f} eV")
    for eps, d in sens:
        print(f"  tail share at mean energy {eps:5.0f} eV: {100 * d:.6f} %")
    for eps, d in interp:
        print(f"  log-log vs linear interpolation at mean energy {eps:5.0f} eV: {100 * d:+.2f} %")
    src = ("e + N2 elastic momentum transfer. Cross section: Song et al., J. Phys. Chem. Ref. Data 52, 023104 (2023), "
           "Table 5 elastic MTCS (Kawaguchi et al. recommendation; 'a few percent'), 0.001 eV-10 keV, transcribed; "
           "linear interpolation in E (log-log differs by " + ", ".join(f"{100 * d:+.2f} % at {eps:.0f} eV" for eps, d in interp)
           + "); held above 10 keV (tail share " + ", ".join(f"{100 * d:.6f} % at {eps:.0f} eV" for eps, d in sens) + "). "
           "Maxwellian-integrated by abep_sim/rate_tables.py (scripts/build_n2_elastic_song2023_table.py). Energy column = "
           "mean electron energy 3/2 Te. Evidence level 4 (docs/EVIDENCE.md). Reaction set abep-n2n-0.3.")
    write_hallthruster_table(OUT, E, sig, 0.0, source=src, tail=TAIL,
                             header_label="Momentum transfer, no inelastic energy loss")
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
