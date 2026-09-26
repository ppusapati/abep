"""Build excitation_N2_rot_j0_to_j2.dat and excitation_N2_rot_j0_to_j4.dat (reaction set abep-n2n-0.10), promoted
(marginally) by the final omitted-process pass (audit/n2_completeness_final_v1.json: gross spectroscopic F_P 1.13 % > 1 %).

Cross sections: Song et al. JPCRD 52, 023104 (2023) Table 6, rotational excitation from j = 0 to j = 2 and j = 4,
0.01-10 eV, transcribed in scripts/audit_n2_completeness_final.py (TABLE6). Above 10 eV sigma is held at its 10 eV value
(declared model: the rate share above 10 eV is negligible where rotational excitation matters, T_e ~ 1-2 eV).
Energy loss: level spacings from NIST Chemistry WebBook (Huber & Herzberg) B_0 = 1.98958 cm^-1: 6 B_0 = 1.480 meV,
20 B_0 = 4.933 meV. Closure limits (as for vibration): gross loss from j = 0 only, no rotational population kinetics, no
superelastic return; at kT_gas >> dE the net loss is much smaller, so this OVER-states rotational cooling.
Usage: python scripts/build_n2_rotational_tables.py
"""
import importlib.util, os, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from abep_sim.rate_tables import write_hallthruster_table   # noqa: E402

_spec = importlib.util.spec_from_file_location("aud", os.path.join(os.path.dirname(__file__), "audit_n2_completeness_final.py"))
aud = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(aud)
PROP = os.path.join(ROOT, "hallthruster_bridge", "propellants")
FILES = {1: "excitation_N2_rot_j0_to_j2.dat", 2: "excitation_N2_rot_j0_to_j4.dat"}


def cross_section(col):
    E = np.array([r[0] for r in aud.TABLE6]); s = np.array([r[col] for r in aud.TABLE6]) * 1e-20
    return E, s


def main():
    for col, f in FILES.items():
        E, s = cross_section(col); dE = round(aud.ROT_DE_SPECTRO_EV[col], 7)
        src = (f"e + N2(j=0) -> e + N2(j={2 * col}). Song et al. JPCRD 2023 Table 6 (0.01-10 eV), held at the 10 eV value above; "
               f"header {dE} eV = {6 if col == 1 else 20} B_0, B_0 = 1.98958 cm^-1 (NIST WebBook, Huber & Herzberg). Gross loss from "
               "j = 0, no superelastic return (over-states net rotational cooling). Maxwellian-integrated by abep_sim/rate_tables.py "
               "(scripts/build_n2_rotational_tables.py). Reaction set abep-n2n-0.10.")
        write_hallthruster_table(os.path.join(PROP, f), E, s, dE, source=src, tail="hold", header_label="Excitation energy")
        print("wrote", f, "dE", dE)


if __name__ == "__main__":
    main()
