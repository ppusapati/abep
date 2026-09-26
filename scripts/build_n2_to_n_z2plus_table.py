"""Build hallthruster_bridge/propellants/dissociative_ionization_N2_to_N_Z2plus.dat (e + N2 -> N_Z2plus + N + 3e: the atomic dication N^2+
produced directly from N2), promoted by the pre-registered audit (audit 1: the N++ column crosses F_ion = 1 % at
T_e >= 25 eV, inside the T_e <= 30 eV domain).

Cross section: Song et al., J. Phys. Chem. Ref. Data 52, 023104 (2023), Table 10, column sigma(N++) (30 points,
70-1000 eV), transcribed in scripts/audit_n2_dissociative_ionization.py (TABLE10_NPP, checked row by row against the PDF
text). The column is the total N++ yield from N2; JPCRD Fig. 24 separates a smaller triple-ionization part (N++ + N+,
Eq. 9). The model channel is N++ + N; the N+ that triple events also produce is not added (a small under-count of N+).
Threshold treatment (same rule as the single dissociative ionization): linear ramp from sigma = 0 at
  E_th = D0(N2) + IE(N I) + IE(N II) = 9.75 + 14.53413 + 29.60125 = 53.885 eV to the published 70 eV point.
Header 53.885 eV = appearance energy (minimum fixed sink; fragment kinetic energy not added).
Above 1000 eV the last value is held (tail share printed). This script also prints the direct-vs-sequential atomic N^2+ (N_Z2plus) source
comparison (sequential: ionization_N_Z1plus_to_N_Z2plus.dat, Bell et al. 1983).
Usage: python scripts/build_n2_to_n_z2plus_table.py
"""
import importlib.util, os, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from abep_sim.rate_tables import maxwellian_rate, tail_sensitivity, write_hallthruster_table   # noqa: E402

_spec = importlib.util.spec_from_file_location("audit", os.path.join(os.path.dirname(__file__), "audit_n2_dissociative_ionization.py"))
audit = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(audit)

OUT = os.path.join(ROOT, "hallthruster_bridge", "propellants", "dissociative_ionization_N2_to_N_Z2plus.dat")
E_TH = round(9.75 + 14.53413 + 29.60125, 3)
TAIL = "hold"


def cross_section(threshold="ramp"):
    E = np.array([r[0] for r in audit.TABLE10_NPP], float); s = np.array([r[1] for r in audit.TABLE10_NPP], float)
    if threshold == "ramp":
        E, s = np.concatenate([[E_TH], E]), np.concatenate([[0.0], s])
    elif threshold == "envelope":
        E, s = np.concatenate([[E_TH], E]), np.concatenate([[s[0]], s])
    elif threshold != "table":
        raise ValueError(threshold)
    return E, s * 1e-20


def main():
    E, s = cross_section()
    sens = tail_sensitivity(E, s, [45, 150, 255])
    print(f"sigma(N++): {len(E)} points, {E[0]}-{E[-1]:.0f} eV; tail share " + ", ".join(f"{100 * d:.3f} % at {e:.0f} eV" for e, d in sens))
    print(" T_e   k_direct(N2->N_Z2plus)  k_seq(N_Z1plus->N_Z2plus)  n_N+/n_N2 at which sequential = 5 % / 100 % of direct")
    for Te in (10, 15, 20, 25, 30):
        kd = maxwellian_rate(E, s, Te, TAIL); ks = audit.table_rate("ionization_N_Z1plus_to_N_Z2plus.dat", Te)
        thr = {t: maxwellian_rate(*cross_section(t), Te, TAIL) / kd - 1 for t in ("table", "envelope")}
        print(f" {Te:4.1f} {kd:.3e}         {ks:.3e}      {0.05 * kd / ks:.2e} / {kd / ks:.2e}   "
              f"(threshold table/envelope vs ramp {100 * thr['table']:+.1f}/{100 * thr['envelope']:+.1f} %)")
    src = ("e + N2 -> N_Z2plus + N + 3e (atomic N^2+). Cross section: Song et al., J. Phys. Chem. Ref. Data 52, 023104 (2023), Table 10 sigma(N++) "
           f"(total N++ yield; triple events' extra N+ not added), linear ramp from 0 at E_th = {E_TH} eV to the 70 eV point; held "
           "above 1000 eV (tail share " + ", ".join(f"{100 * d:.3f} % at {e:.0f} eV" for e, d in sens) + f"). Header {E_TH} eV = "
           "appearance energy. Maxwellian-integrated by abep_sim/rate_tables.py (scripts/build_n2_to_n_z2plus_table.py). "
           "Evidence level 4. Reaction set abep-n2n-0.6.")
    write_hallthruster_table(OUT, E, s, E_TH, source=src, tail=TAIL)
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
