"""Build the N2 dissociative-ionization tables (e + N2 -> N+ + N + 2e), promoted by the pre-registered omitted-process
audit (hallthruster_bridge/audit/n2_dissociative_ionization_v1.json; prereg n2_completeness_audit_v1).

Cross section: Song et al., J. Phys. Chem. Ref. Data 52, 023104 (2023), Table 10, column sigma(N+ + N2++) (38 points,
30-1000 eV; +-5 % on the evaluated set, Sec. 2.8), transcribed in scripts/audit_n2_dissociative_ionization.py
(TABLE10_NPLUS, checked row by row against the PDF text). N+ and the molecular dication N2++ (same m/q) are not separated
in that column; JPCRD Sec. 2.8 states N2++ is ~1 % of the total ionization cross section and gives no recommended N2++
values. The ambiguity is carried as two chemistry variants instead of being resolved silently:
  upper (n2_n.toml):        sigma_DI = sigma(N+ + N2++)                       (published column; conservative N+ source)
  lower (n2_n_di_lower.toml): sigma_DI = sigma(N+ + N2++) - 0.01 sigma_total  (the "~1 %" statement applied at every
                              energy; statement-derived, approximate)
Threshold treatment (owner decision 2026-09-26): nominal = linear ramp from sigma(E_th) = 0 at
  E_th = D0(N2) + IE(N) = 9.75 + 14.534 = 24.284 eV to the published 30 eV point. Sensitivity bounds, recorded and not
  used as tables: sigma = 0 below 30 eV ("table") and sigma(30 eV) held down to E_th ("envelope").
Header energy loss 24.284 eV (owner decision): the appearance energy is the defensible minimum fixed sink. Fragment
  kinetic energy (0-16 eV) is incident-energy dependent and is not added as a constant; 24.28-40.28 eV is carried as a
  sensitivity (electron-power share printed).
Above 1000 eV the last value is held (tail share printed). Molecular N2++ stays a separate, unresolved channel.
Usage: python scripts/build_n2_dissociative_ionization_table.py
"""
import importlib.util, os, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from abep_sim.rate_tables import maxwellian_rate, tail_sensitivity, write_hallthruster_table   # noqa: E402

_spec = importlib.util.spec_from_file_location("audit", os.path.join(os.path.dirname(__file__), "audit_n2_dissociative_ionization.py"))
audit = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(audit)
_spec = importlib.util.spec_from_file_location("iz", os.path.join(os.path.dirname(__file__), "build_n2_ionization_song2023_table.py"))
iz = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(iz)

PROP = os.path.join(ROOT, "hallthruster_bridge", "propellants")
E_TH = audit.E_TH_DI                   # 24.284 eV
KER_MAX_EV = audit.KER_MAX_EV          # 16 eV
N2PP_FRACTION_OF_TOTAL = 0.01          # JPCRD 2023 Sec. 2.8: "~1% of the total ionization cross section"
TAIL = "hold"
FILES = {"upper": "dissociative_ionization_N2_upper.dat", "lower": "dissociative_ionization_N2_lower.dat"}


def cross_section(variant="upper", threshold="ramp"):
    E = np.array([r[0] for r in audit.TABLE10_NPLUS], float)
    s = np.array([r[1] for r in audit.TABLE10_NPLUS], float)
    if variant == "lower":
        tot = {r[0]: r[2] for r in iz.TABLE10}
        s = s - N2PP_FRACTION_OF_TOTAL * np.array([tot[e] for e in E])
        assert (s > 0).all()
    elif variant != "upper":
        raise ValueError(variant)
    if threshold == "ramp":
        E, s = np.concatenate([[E_TH], E]), np.concatenate([[0.0], s])
    elif threshold == "envelope":
        E, s = np.concatenate([[E_TH], E]), np.concatenate([[s[0]], s])
    elif threshold != "table":
        raise ValueError(threshold)
    return E, s * 1e-20                # 1e-16 cm^2 = 1e-20 m^2


def threshold_sensitivity(Te_values, variant="upper"):
    out = []
    for Te in Te_values:
        k = {t: maxwellian_rate(*cross_section(variant, t), Te, TAIL) for t in ("table", "ramp", "envelope")}
        out.append((float(Te), k["table"] / k["ramp"] - 1, k["envelope"] / k["ramp"] - 1))
    return out


def main():
    Tes = [3, 5, 10, 20, 30]
    for v, f in FILES.items():
        E, s = cross_section(v)
        sens = tail_sensitivity(E, s, [45, 150, 255])
        thr = threshold_sensitivity(Tes, v)
        print(f"{v}: {f}, {len(E)} points, {E[0]:.3f}-{E[-1]:.0f} eV")
        for Te, lo, hi in thr:
            print(f"  T_e {Te:4.1f} eV: rate(table)/rate(ramp) - 1 = {100 * lo:+.1f} %, rate(envelope)/rate(ramp) - 1 = {100 * hi:+.1f} %")
        src = (f"e + N2 -> N+ + N + 2e ({v} variant). Cross section: Song et al., J. Phys. Chem. Ref. Data 52, 023104 (2023), "
               "Table 10 sigma(N+ + N2++)" + (" minus 0.01 x sigma_total (JPCRD Sec. 2.8 '~1 %' N2++ statement)" if v == "lower" else "")
               + f"; linear ramp from 0 at E_th = {E_TH:.3f} eV to the 30 eV point; held above 1000 eV (tail share "
               + ", ".join(f"{100 * d:.3f} % at {e:.0f} eV" for e, d in sens) + "). Threshold sensitivity vs ramp (table / envelope): "
               + ", ".join(f"T_e {Te:g} eV {100 * lo:+.1f}/{100 * hi:+.1f} %" for Te, lo, hi in thr)
               + f". Header {E_TH:.3f} eV = appearance energy (minimum fixed sink; +{KER_MAX_EV:.0f} eV kinetic-energy release is a "
               "sensitivity, not included). Maxwellian-integrated by abep_sim/rate_tables.py "
               "(scripts/build_n2_dissociative_ionization_table.py). Evidence level 4. Reaction set abep-n2n-0.4.")
        write_hallthruster_table(os.path.join(PROP, f), E, s, round(E_TH, 3), source=src, tail=TAIL)
        print("  wrote", f)
    # energy-loss sensitivity: extra electron power if 16 eV of fragment kinetic energy were charged per event
    E, s = cross_section("upper")
    for Te in Tes:
        k_di = maxwellian_rate(E, s, Te, TAIL)
        k_iz = audit.table_rate("ionization_N2_song2023.dat", Te); k_d = audit.table_rate("dissociation_N2.dat", Te)
        P = k_iz * 15.58 + k_d * 12.14 + k_di * E_TH
        print(f"  T_e {Te:4.1f} eV: +{KER_MAX_EV:.0f} eV per DI event would add {100 * k_di * KER_MAX_EV / P:.1f} % to P_e "
              "(abep-n2n-0.4 included set, no excitation yet)")


if __name__ == "__main__":
    main()
