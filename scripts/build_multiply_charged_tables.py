"""Build the multiply-charged N / N2 rate tables assessed by the tier-3 closure (n2_completeness_audit_v1 + addenda 1, 2;
verdicts in hallthruster_bridge/audit/n2_closure_verdicts_v1.json).

Bound tables (hallthruster_bridge/audit/bound_tables/, used by checks/blind_state_envelope.jl; never in a reaction set unless
also written below as a propellant table):
  ionization_N_Z2plus_to_N_Z3plus_bell1983.dat     e + N^2+ -> N^3+ + 2e    Bell et al. JPCRD 12, 891 (1983) Eq. (1), N III
                                                                            (Table 5, read from the page image; +-10 %). EXCLUDED.
  ionization_N_to_N_Z2plus_hms2017.dat             e + N -> N^2+ + 3e       Hahn, Muller & Savin, ApJ 850, 122 (2017)
  ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.dat e + N2+ -> N2^2+ + 2e    Tabata et al. ADNDT 92, 375 (2006) QST n2-69 fit
  ionization_N2_to_N2_Z2plus_nominal.dat           e + N2 -> N2^2+ + 3e     0.01 sigma_total (JPCRD 2023 Sec. 2.8), from 42.9 eV
  ionization_N2_to_N2_Z2plus_upper.dat             e + N2 -> N2^2+ + 3e     0.14e-16 cm^2 flat (all double ionization), from 42.9 eV

Propellant tables (abep-n2n-0.11):
  ionization_N_to_N_Z2plus_hms2017.dat            NOMINAL (n2_n.toml): direct N -> N^2+ PROMOTED by F_S(N^2+ production)
  ionization_N_to_N_Z2plus_hms2017_x0p5.dat       sensitivity n2_n_ndd_hmslow.toml
  ionization_N_to_N_Z2plus_hms2017_x1p3.dat       sensitivity n2_n_ndd_hmshigh.toml
      HMS Sec. 3.19: double-ionization cross sections "accurate to ~30 %" (-> x1.3); Sec. 3.7: the same scheme overestimates
      neutral O0+ by about a factor of two (-> x0.5; neutral N has no measurement and was not corrected).
  ionization_N2_to_N2_Z2plus_upper.dat            UNCERTAINTY VARIANT n2_n_n2dication.toml (molecular N2^2+: nominal < 1 % <
  ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.dat   upper; both routes; N2 max_charge = 2; the sequential route supplies the
                                                     one-to-one N2+ -> N2^2+ link HallThruster.jl needs for the N2^2+ energy;
                                                     header 42.9 - 15.58 = 27.32 eV so both routes give one N2^2+ energy)

HMS formulae (arXiv:1708.02155, identical in ApJ): Eq. (2) sigma_D = (1 - exp(-3(u-1))) p0/Eth^3 (u-1)/(u+0.5)^2 x 1e-13 cm^2;
Eq. (3) sigma_IA = fBR p0/Eth^2 (u-1)/(u(u+p1)) x 1e-13 cm^2; parameters VizieR J/ApJ/850/122 table2 rows (Z=7, qi=0, qf=2):
Eq. 2: Eth 44.1354 eV, f 1, p0 43; Eq. 3: Eth 403 eV, fBR 0.9926, p0 3.6, p1 5 (table2.dat sha256 fa3d95a6...).
Semi-empirical: HMS Table 1 lists no neutral-N double-ionization measurement (N-like scheme from O1+, Ne3+, Ar11+).
Tabata n2-69 (QST open data, files n2-69.f sha256 bb7e8819..., n2-69.dat sha256 205beb5b...): sigma = 1e-16 a1 (ln(E/Eth) + a2) /
(Eth E (1 + a3/(E - Eth))^a4) cm^2, E in keV, Eth = 27.9 eV, a1..a4 = 4.080e-5, 170.0, 0.282, 1.026; fit/data 0.86-1.11 vs Bahati
et al. J. Phys. B 34, 2963 (2001), fit range 29 eV - 2.5 keV.
Usage: python scripts/build_multiply_charged_tables.py [--check]   (--check: rebuild in memory and compare with the files)
"""
import importlib.util, os, sys, tempfile, filecmp
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from abep_sim.rate_tables import write_hallthruster_table   # noqa: E402

BOUND = os.path.join(ROOT, "hallthruster_bridge", "audit", "bound_tables")
PROP = os.path.join(ROOT, "hallthruster_bridge", "propellants")
HMS_D = (44.1354, 43.0)                     # Eth, p0 (Eq. 2, f = 1)
HMS_IA = (403.0, 0.9926, 3.6, 5.0)          # Eth, fBR, p0, p1 (Eq. 3)
HMS_BAND = {"x0p5": 0.5, "x1p3": 1.3}
TABATA_N2_69 = (27.9, 4.080e-5, 1.700e2, 2.820e-1, 1.026)
N2Z2_APPEARANCE = 42.9                      # eV, Mark 1975 (as cited by the owner), +-0.3


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(__file__), name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def hms_sigma(E):
    """HMS direct (Eq. 2) + K-shell IA (Eq. 3) N -> N^2+ cross section [m^2]."""
    Eth, p0 = HMS_D
    u = E / Eth
    sD = np.where(E > Eth, (1 - np.exp(-3 * (u - 1))) * p0 / Eth ** 3 * (u - 1) / (u + 0.5) ** 2, 0.0)
    EI, f, q0, q1 = HMS_IA
    uI = E / EI
    sIA = np.where(E > EI, f * q0 / EI ** 2 * (uI - 1) / (uI * (uI + q1)), 0.0)
    return (sD + sIA) * 1e-17


def hms_grid():
    Eth = HMS_D[0]
    return np.concatenate([[Eth], np.geomspace(Eth * 1.0001, 1e4, 800)])


def tabata69(E_eV):
    """Tabata et al. 2006 n2-69 fit, e + N2+ -> N2^2+ [m^2]."""
    E = np.asarray(E_eV) / 1e3; Eth = TABATA_N2_69[0] / 1e3; a1, a2, a3, a4 = TABATA_N2_69[1:]
    with np.errstate(invalid="ignore", divide="ignore"):
        s = 1e-16 * a1 * (np.log(E / Eth) + a2) / (Eth * E * (1. + (a3 / (E - Eth))) ** a4)
    return np.where(E > Eth, s, 0.0) * 1e-4


def bell_n3(E):
    I, A, B = _load("audit_n2_completeness_final").BELL_N_III
    x = 1 - I / E
    s = (A * np.log(E / I) + sum(b * x ** (i + 1) for i, b in enumerate(B))) / (I * E) * 1e-17
    return np.where(E > I, s, 0.0)


def tables():
    """(directory, file, E, sigma, header energy, source) for every table this script owns."""
    out = []
    I = _load("audit_n2_completeness_final").BELL_N_III[0]
    E = np.concatenate([[I], np.geomspace(I * 1.0001, 1e4, 600)])
    out.append((BOUND, "ionization_N_Z2plus_to_N_Z3plus_bell1983.dat", E, bell_n3(E), 47.4453,
                "BOUND ONLY (not in any reaction set): e + N^2+ -> N^3+ + 2e, Bell et al. JPCRD 12, 891 (1983) Eq. (1), Table 5 N III "
                "(I = 47.45 eV, A = 0.5004, B = 0.2234, 2.2074, -4.1555, 3.7686; +-10 %). Used by hallthruster_bridge/checks/blind_state_envelope.jl."))
    hms_src = ("Hahn, Muller & Savin, ApJ 850, 122 (2017), VizieR J/ApJ/850/122 table2 (Z=7, qi=0, qf=2): Eq. (2) direct DI "
               "(Eth 44.1354 eV, p0 43, f 1) + Eq. (3) K-shell IA (Eth 403 eV, fBR 0.9926, p0 3.6, p1 5). Semi-empirical; NO "
               "experimental neutral-N data in their Table 1 (N-like scheme from ions).")
    E = hms_grid()
    out.append((BOUND, "ionization_N_to_N_Z2plus_hms2017.dat", E, hms_sigma(E), HMS_D[0],
                "BOUND ONLY (not in any reaction set): e + N -> N^2+ + 3e, " + hms_src + " Used by checks/blind_state_envelope.jl."))
    out.append((PROP, "ionization_N_to_N_Z2plus_hms2017.dat", E, hms_sigma(E), HMS_D[0],
                "e + N -> N^2+ + 3e (direct double ionization), NOMINAL (abep-n2n-0.11; promoted by F_S(N^2+ production) 63-85 % in all "
                "180 blind-envelope runs, audit/n2_closure_verdicts_v1.json). " + hms_src + " Sensitivity x0.5 / x1.3: HMS Sec. 3.7 / 3.19. "
                "Built by scripts/build_multiply_charged_tables.py."))
    for tag, f in HMS_BAND.items():
        out.append((PROP, f"ionization_N_to_N_Z2plus_hms2017_{tag}.dat", E, f * hms_sigma(E), HMS_D[0],
                    f"e + N -> N^2+ + 3e, HMS 2017 x {f} SENSITIVITY branch (abep-n2n-0.11; "
                    + ("HMS Sec. 3.7: the same semi-empirical scheme overestimates neutral O0+ by about a factor of two" if f < 1
                       else "HMS Sec. 3.19: double-ionization cross sections accurate to ~30 %")
                    + "). " + hms_src + " Built by scripts/build_multiply_charged_tables.py."))
    E = np.concatenate([[TABATA_N2_69[0]], np.geomspace(TABATA_N2_69[0] * 1.0001, 1e4, 800)])
    tab_src = ("e + N2+ -> N2^2+ + 2e ('single ionization' of N2+), Tabata, Shirai, Sataka & Kubo, At. Data Nucl. Data Tables 92, "
               "375 (2006), QST n2-69 analytic fit (E_th = 27.9 eV, 29 eV-2.5 keV) to Bahati et al., J. Phys. B 34, 2963 (2001); held "
               "above 2.5 keV. QST files sha256 n2-69.f bb7e8819..., n2-69.dat 205beb5b....")
    out.append((BOUND, "ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.dat", E, tabata69(E), TABATA_N2_69[0],
                "BOUND ONLY: " + tab_src + " Used by checks/blind_state_envelope.jl."))
    iz = _load("build_n2_ionization_song2023_table")
    seq_header = round(N2Z2_APPEARANCE - iz.THRESHOLD_EV, 4)
    out.append((PROP, "ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.dat", E, tabata69(E), seq_header,
                tab_src + f" Header {seq_header} eV = N2^2+ appearance energy 42.9 eV (Mark 1975) - N2 ionization header "
                f"{iz.THRESHOLD_EV} eV, so that HallThruster.jl derives one N2^2+ energy from both routes (the fit threshold 27.9 eV "
                "is kept in the cross section; the 0.58 eV header difference is an energy-loss convention). Molecular N2^2+ UNCERTAINTY VARIANT only (n2_n_n2dication.toml, abep-n2n-0.11). Built by "
                "scripts/build_multiply_charged_tables.py."))
    Et = np.array([r[0] for r in iz.TABLE10], float); St = np.array([r[2] for r in iz.TABLE10]) * 1e-20
    th = N2Z2_APPEARANCE; m = Et >= th
    out.append((BOUND, "ionization_N2_to_N2_Z2plus_nominal.dat", np.concatenate([[th], Et[m]]), np.concatenate([[0.0], 0.01 * St[m]]), th,
                "BOUND ONLY: e + N2 -> N2^2+ + 3e nominal envelope: 0.01 x sigma_total (JPCRD 2023 Table 10; Sec. 2.8 '~1 % of the total "
                "ionization cross section') from the 42.9 +- 0.3 eV appearance energy (Mark 1975, as cited by the owner)."))
    Eu = np.array([th, np.nextafter(th, np.inf), 1e4]); Su = np.array([0, 0.14e-20, 0.14e-20])
    up_src = ("e + N2 -> N2^2+ + 3e loose upper envelope: 0.14e-16 cm^2 flat (maximum total double ionization, Tian & Vidal via "
              "JPCRD 2023 Sec. 2.8) from 42.9 eV.")
    out.append((BOUND, "ionization_N2_to_N2_Z2plus_upper.dat", Eu, Su, th, "BOUND ONLY: " + up_src))
    out.append((PROP, "ionization_N2_to_N2_Z2plus_upper.dat", Eu, Su, th,
                up_src + " Molecular N2^2+ UNCERTAINTY VARIANT only (n2_n_n2dication.toml, abep-n2n-0.11): it represents the "
                "threshold-crossing envelope (nominal < 1 % < upper), not asserted physics. Built by scripts/build_multiply_charged_tables.py."))
    return out


def main():
    check = "--check" in sys.argv
    bad = []
    for d, name, E, s, th, src in tables():
        if check:
            with tempfile.TemporaryDirectory() as t:
                p = os.path.join(t, name); write_hallthruster_table(p, E, s, th, source=src)
                same = os.path.exists(os.path.join(d, name)) and filecmp.cmp(p, os.path.join(d, name), shallow=False)
            print(("same   " if same else "DIFFERS"), os.path.relpath(os.path.join(d, name), ROOT))
            same or bad.append(name)
        else:
            write_hallthruster_table(os.path.join(d, name), E, s, th, source=src)
            print("wrote", os.path.relpath(os.path.join(d, name), ROOT))
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
