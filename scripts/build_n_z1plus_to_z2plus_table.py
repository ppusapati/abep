"""Build hallthruster_bridge/propellants/ionization_N_Z1plus_to_N_Z2plus.dat (e + N_Z1plus -> N_Z2plus + 2e (atomic N+ -> N^2+), sequential ionization).

Why it exists: the pre-registered audit promoted atomic N^2+ (N_Z2plus) production (n2_completeness_audit_v1; N++ column of JPCRD 2023
Table 10 crosses F_ion = 1 % inside T_e <= 30 eV), so atomic N gets max_charge = 2. HallThruster.jl derives each species'
energy only through one-to-one reactions, so N_Z2plus needs this N_Z1plus -> N_Z2plus link to load at all; it is also the sequential
source route that must not be ignored once N_Z2plus exists.

Cross section: Bell, Gilbody, Hughes, Kingston & Smith, "Recommended data on the electron impact ionization of light atoms
and ions", J. Phys. Chem. Ref. Data 12, 891 (1983), doi:10.1063/1.555700, Eq. (1) with the N II parameters of Table 5
(read from the page image of the NIST-hosted reprint https://srd.nist.gov/jpcrdreprint/1.555700.pdf, sha256
2427d619172a06ccf49e20af3cc0ab44a17e58262902600502786351f52261df; not committed):
    sigma(E) = [A ln(E/I) + sum_i B_i (1 - I/E)^i] / (I E)   [cm^2, with A, B_i in 1e-13 eV^2 cm^2, E, I in eV]
    N II: I = 29.60 eV, A = 1.0755, B = (-0.8287, 0.8724, -0.1618, 1.5331), reliability +-10 % (67 % confidence).
Bell et al. base N II on the crossed-beam data of Harrison et al., extrapolated beyond 500 eV with Eq. (1); the beam's
metastable N+ content is not stated in Bell's Table 5 (no metastable flag) - verify against Harrison et al. if it matters.
Formula check: the same Eq. (1) with the N I row reproduces NIST SRD 107 Kim & Desclaux (30 % 2D mix, the Brook et al.
beam that Bell follow) to within 1-5 % from 30 eV to 1 keV (checked 2026-09-26, docs/HISTORY.md; BELL["N I"] is kept for that check).

Evidence (docs/EVIDENCE.md): level 4 (evaluated literature); quantity type: evaluated measurement, fitted analytic form
(parameters transcribed, no digitization). Transformation chain: Harrison et al. measurements -> Bell et al. recommended
curve -> Eq. (1) fit (Table 5) -> evaluated here on 29.60 eV - 10 keV (log grid) -> Maxwellian integration.
Header energy 29.60125 eV = IE(N II), NIST ASD (bracketed there: not purely experimental).
Usage: python scripts/build_n_z1plus_to_z2plus_table.py
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from abep_sim.rate_tables import tail_sensitivity, write_hallthruster_table   # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "hallthruster_bridge", "propellants", "ionization_N_Z1plus_to_N_Z2plus.dat")
HEADER_EV = 29.60125
BELL = {"N I": (14.53, 2.2648, (-1.7100, -2.3220, 1.7324)),
        "N II": (29.60, 1.0755, (-0.8287, 0.8724, -0.1618, 1.5331))}
TAIL = "hold"


def bell_sigma_m2(E, species="N II"):
    I, A, B = BELL[species]
    E = np.asarray(E, float); x = 1 - I / E
    s = (A * np.log(E / I) + sum(b * x ** (i + 1) for i, b in enumerate(B))) / (I * E) * 1e-13 * 1e-4   # cm^2 -> m^2
    return np.where(E > I, s, 0.0)


def grid():
    I = BELL["N II"][0]
    return np.concatenate([[I], np.geomspace(I * 1.0001, 1e4, 600)])


def main():
    E = grid(); s = bell_sigma_m2(E)
    assert (s >= 0).all()
    sens = tail_sensitivity(E, s, [45, 150, 255])
    print(f"N II Bell et al. 1983: max {s.max():.3e} m^2 at {E[s.argmax()]:.0f} eV; tail share "
          + ", ".join(f"{100 * d:.4f} % at {e:.0f} eV" for e, d in sens))
    src = ("e + N_Z1plus -> N_Z2plus + 2e (atomic N+ -> N^2+). Cross section: Bell et al., J. Phys. Chem. Ref. Data 12, 891 (1983), Eq. (1), Table 5 N II "
           "(I = 29.60 eV, A = 1.0755, B = -0.8287, 0.8724, -0.1618, 1.5331; +-10 %), evaluated 29.60 eV-10 keV; held above "
           "(tail share " + ", ".join(f"{100 * d:.4f} % at {e:.0f} eV" for e, d in sens) + "). "
           f"Header {HEADER_EV} eV = IE(N II), NIST ASD. Maxwellian-integrated by abep_sim/rate_tables.py "
           "(scripts/build_n_z1plus_to_z2plus_table.py). Evidence level 4. Reaction set abep-n2n-0.5.")
    write_hallthruster_table(OUT, E, s, HEADER_EV, source=src, tail=TAIL)
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
