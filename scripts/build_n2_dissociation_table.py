"""Build hallthruster_bridge/propellants/dissociation_N2.dat (e + N2 -> N + N + e, dissociation into neutrals).

Cross section: Song, Cho, Karwasz, Kokoouline & Tennyson, "Cross Sections for Electron Collisions with N2, N2*, and N2+",
J. Phys. Chem. Ref. Data 52, 023104 (2023), doi:10.1063/5.0150618, Table 9 ("Recommended dissociation cross sections of
N2"), uncertainty +-20 % (Sec. 2.7). Read from the NSF Public Access Repository copy (https://par.nsf.gov/servlets/purl/10526876,
sha256 f35b73d1f5f11291e6d844cdd8e324f99b6f5b17a9661d2568fca59e9604875d); the PDF is not committed. The recommended set is
Cosby, J. Chem. Phys. 98, 9544 (1993): his weighted averages between his own neutral-fragment measurement and Winters,
J. Chem. Phys. 44, 1472 (1966). Same set recommended by Itikawa 2006 and by the CC BY 4.0 companion paper Song et al.,
Eur. Phys. J. D 77, 105 (2023), Fig. 6.

Evidence (docs/EVIDENCE.md): level 4 (evaluated literature); quantity type: evaluated measurement, transcribed from a
numeric table (no digitization). Transformation chain:
  Cosby 1993 + Winters 1966 measurements -> Cosby weighted average -> JPCRD 2023 Table 9 (16 points, 12-200 eV)
  -> transcribed here -> Maxwellian integration (abep_sim/rate_tables.py).
Choices made here, all explicit:
  * sigma = 0 below 12 eV (the first tabulated point). No threshold curve is constructed between the 9.75 eV bond energy
    and 12 eV.
  * Above 200 eV the last value is held ("hold" tail). This is an extrapolation assumption; the script prints how much of
    each rate rests on it (hold vs zero tail). It is < 1 % for mean energy <= 45 eV (T_e <= 30 eV).
  * Header energy = 12.14 eV, the N(2D) + N(4S) channel threshold: a representative fixed energy loss for a
    channel-summed dissociation cross section, NOT a universal measured energy loss per dissociation event. Cosby concluded
    from translational-energy spectra at 48.5 eV that this is the dominant pattern and that N(4S) + N(4S) (9.75 eV) is
    not significant (JPCRD 2023 Sec. 2.7). The table itself is the channel-summed N + N cross section. The range
    9.75-13.33 eV (N(4S)+N(4S) to N(2P)+N(4S)) is carried as a model uncertainty on the energy loss. HallThruster.jl reads the energy only from this header line.
Usage: python scripts/build_n2_dissociation_table.py
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from abep_sim.rate_tables import tail_sensitivity, write_hallthruster_table   # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "hallthruster_bridge", "propellants", "dissociation_N2.dat")
ENERGY_LOSS_EV = 12.14          # N2 -> N(2D) + N(4S) threshold (JPCRD 2023 Eq. 5)
TAIL = "hold"

# JPCRD 52, 023104 (2023), Table 9: electron energy [eV], N + N cross section [1e-16 cm^2]
TABLE9 = [(12, 0.01), (14, 0.04), (16, 0.2), (18, 0.36), (20, 0.52), (25, 0.87), (30, 1.04), (40, 1.15), (50, 1.23),
          (60, 1.23), (80, 1.2), (100, 1.16), (125, 1.1), (150, 1.04), (175, 0.99), (200, 0.95)]


def main():
    E = np.array([e for e, _ in TABLE9], float)
    sig = np.array([s for _, s in TABLE9], float) * 1e-20     # 1e-16 cm^2 = 1e-20 m^2
    sens = tail_sensitivity(E, sig, [15, 30, 45, 60, 90, 150, 300])
    print(f"Table 9: {len(E)} points, {E[0]:.0f}-{E[-1]:.0f} eV, max {sig.max():.3e} m^2 at {E[sig.argmax()]:.0f} eV")
    print("tail sensitivity (rate share resting on sigma held beyond 200 eV):")
    for eps, d in sens:
        print(f"  mean energy {eps:5.0f} eV (T_e {eps / 1.5:5.1f} eV): {100 * d:6.2f} %")
    src = ("e + N2 -> N + N + e (dissociation into neutrals, channel-summed). Cross section: Song et al., J. Phys. Chem. "
           "Ref. Data 52, 023104 (2023), Table 9 (Cosby 1993 recommended set, +-20 %), transcribed. sigma = 0 below 12 eV; "
           f"held at the 200 eV value above 200 eV (tail sensitivity: " +
           ", ".join(f"{100 * d:.2f} % at {eps:.0f} eV" for eps, d in sens) + "). "
           f"Header energy {ENERGY_LOSS_EV} eV = N(2D)+N(4S) threshold (dominant channel, Cosby 1993): a representative fixed "
           "energy loss for a channel-summed cross section, not a universal measured loss per event; model uncertainty "
           "9.75-13.33 eV. Validity domain: mean energy <= 45 eV (T_e <= 30 eV). "
           "Maxwellian-integrated by abep_sim/rate_tables.py (scripts/build_n2_dissociation_table.py). "
           "Energy column = mean electron energy 3/2 Te. Evidence level 4 (docs/EVIDENCE.md).")
    write_hallthruster_table(OUT, E, sig, ENERGY_LOSS_EV, source=src, tail=TAIL,
                             header_label="Dissociation energy loss")
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
