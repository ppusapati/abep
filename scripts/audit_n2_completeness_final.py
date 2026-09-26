"""Omitted-process audit, final pass (prereg n2_completeness_audit_v1), on reaction set abep-n2n-0.9:
  * rerun of audit 1 (dissociative ionization) and audit 2 (vibrational excitation) with the complete 0.9 denominators;
  * the three tier-3 bounds: rotational excitation, N^2+ -> N^3+ (N_Z2plus -> N_Z3plus), direct N -> N^2+.

Denominators are built from n2_n.toml itself: every N2-target inelastic reaction's committed rate table k_r(3/2 T_e) times
its header energy (elastic channels carry no inelastic loss), per unit N2 density with atomic fraction x_N = 0 (atomic N
only adds to denominators, so x_N = 0 maximises every fraction). Shares are reported as the omitted/included channel's
share of the TOTAL (the channel itself counted once in the denominator).

Rotational excitation (JPCRD 2023 Table 6, j = 0 -> 2 and 0 -> 4, 0.01-10 eV, transcribed below): bounded, not modelled.
  Conservative choices: sigma held at its table MAXIMUM above 10 eV (upper envelope; the table ends while sigma(0->2) is
  still rising); energy per event <= 0.010 eV for both transitions (a ceiling). A second, spectroscopic bound uses the
  actual level spacings from NIST Chemistry WebBook (Huber & Herzberg), X 1Sigma_g+: B_e = 1.99824 cm^-1,
  alpha_e = 0.017318 cm^-1 -> B_0 = B_e - alpha_e/2 = 1.98958 cm^-1; dE(0->2) = 6 B_0 = 1.480 meV, dE(0->4) = 20 B_0 = 4.933 meV,
  with sigma held at its 10 eV value above 10 eV. Both are GROSS losses from j = 0 with no superelastic credit; at gas
  temperature kT ~ 26-43 meV >> dE, detailed balance makes the NET rotational loss much smaller (not quantified here).
N^2+ -> N^3+ (Bell et al. JPCRD 1983 Eq. (1), Table 5 N III row read from the page image: I = 47.45 eV, A = 0.5004,
  B = 0.2234, 2.2074, -4.1555, 3.7686; +-10 %): its share of total positive-ion production depends on n(N^2+)/n(N2), so the
  bound is reported as the ratio x_crit at which it would reach the 1 % F_ion criterion.
  Reference-state check (full abep-n2n-0.9 set, N1 smoke run, 0.5 ms, default transport, no measured targets; driver
  profiles profile_ni_*): max n(N^2+)/n(N2) = 1.2e-3 (at T_e ~ 2 eV), domain-integrated F_ion = 4.7e-7, N^2+ destroyed by
  ionization = 2.1e-4 of its production -> x_crit is exceeded nowhere by a factor ~200 (REFERENCE_STATE below).
Direct N -> N^2+: no cross-section source in hand; per owner rule it is NOT inferred from sequential ionization or scaled.
  Recorded as unresolved-by-source.
Usage: python scripts/audit_n2_completeness_final.py  (writes hallthruster_bridge/audit/n2_completeness_final_v1.json)
"""
import importlib.util, json, os, sys, tomllib
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from abep_sim.rate_tables import maxwellian_rate   # noqa: E402

PROP = os.path.join(ROOT, "hallthruster_bridge", "propellants")
PREREG = os.path.join(ROOT, "hallthruster_bridge", "prereg", "n2_completeness_audit_v1.json")
OUT = os.path.join(ROOT, "hallthruster_bridge", "audit", "n2_completeness_final_v1.json")
_spec = importlib.util.spec_from_file_location("bell", os.path.join(os.path.dirname(__file__), "build_n_z1plus_to_z2plus_table.py"))
bell = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bell)
BELL_N_III = (47.45, 0.5004, (0.2234, 2.2074, -4.1555, 3.7686))
ROT_DE_CEILING_EV = 0.010
CM1_TO_EV = 1.239841984e-4
B0_CM1 = 1.99824 - 0.017318 / 2                          # NIST WebBook X 1Sigma_g+ (Huber & Herzberg)
ROT_DE_SPECTRO_EV = {1: 6 * B0_CM1 * CM1_TO_EV, 2: 20 * B0_CM1 * CM1_TO_EV}   # column 1: j 0->2, column 2: j 0->4
# JPCRD 52, 023104 (2023) Table 6: E [eV], sigma(j 0->2), sigma(j 0->4) [1e-16 cm^2]
TABLE6 = [(0.01, 0.320, 0.004), (0.23, 0.342, 0.004), (0.45, 0.372, 0.005), (0.67, 0.407, 0.007), (0.89, 0.447, 0.013),
          (1.12, 0.492, 0.027), (1.34, 0.545, 0.060), (1.56, 0.611, 0.136), (1.78, 0.707, 0.315), (2.00, 0.882, 0.767),
          (2.10, 1.029, 1.199), (2.21, 1.264, 1.928), (2.31, 1.663, 3.194), (2.41, 2.362, 5.425), (2.52, 3.525, 9.095),
          (2.62, 4.993, 13.580), (2.72, 5.772, 15.651), (2.83, 5.326, 13.808), (2.93, 4.441, 10.713), (3.03, 3.695, 8.171),
          (3.14, 3.172, 6.389), (3.24, 2.818, 5.167), (3.34, 2.579, 4.313), (3.45, 2.413, 3.697), (3.55, 2.298, 3.241),
          (3.66, 2.218, 2.893), (3.76, 2.162, 2.622), (3.86, 2.124, 2.407), (3.97, 2.099, 2.232), (4.07, 2.085, 2.089),
          (4.17, 2.078, 1.969), (4.28, 2.077, 1.868), (4.38, 2.080, 1.782), (4.48, 2.088, 1.708), (4.59, 2.099, 1.644),
          (4.69, 2.112, 1.588), (4.79, 2.127, 1.538), (4.90, 2.144, 1.495), (5.00, 2.163, 1.455), (5.56, 2.275, 1.302),
          (6.11, 2.399, 1.204), (6.67, 2.523, 1.135), (7.22, 2.642, 1.083), (7.78, 2.756, 1.040), (8.33, 2.863, 1.005),
          (8.89, 2.964, 0.973), (9.44, 3.058, 0.945), (10.00, 3.151, 0.919)]
REFERENCE_STATE = {"source": "N1 smoke run, abep-n2n-0.9 n2_n.toml, 0.5 ms, default transport (docs/HISTORY.md 2026-09-26)",
                   "max_N_Z2plus_over_N2": 1.16e-3, "F_ion_N_Z2plus_to_N_Z3plus": 4.72e-7, "F_S_N_Z2plus_destruction": 2.14e-4}
ION_PRODUCING = ("N2 + e -> N2(+) + 2e", "N2 + e -> N(+) + N + 2e", "N2 + e -> N(2+) + N + 3e")


def load_table(f):
    a = np.loadtxt(os.path.join(PROP, f), skiprows=2)
    head = open(os.path.join(PROP, f)).readline()
    dE = float(head.split(":")[1]) if ":" in head else 0.0
    return a, dE


def n2_reactions(config="n2_n.toml"):
    """(label, file, energy loss, is_ion_producing) for every N2-target inelastic reaction in the config."""
    cfg = tomllib.load(open(os.path.join(PROP, config), "rb"))
    out = []
    for r in cfg["reactions"]:
        if r["type"] == "elastic":
            continue
        eq = r.get("equation", "")
        target = r.get("target_species") or eq.split("+")[0].strip()
        if target != "N2":
            continue
        _, dE = load_table(r["rate_coeff_file"])
        out.append((eq or f"excitation {r['rate_coeff_file']}", r["rate_coeff_file"], dE, eq in ION_PRODUCING))
    return out


def k_of(f, Te):
    a, _ = load_table(f)
    return float(np.interp(1.5 * Te, a[:, 0], a[:, 1]))


def budget(Te, config="n2_n.toml"):
    P, K_ion, parts = 0.0, 0.0, {}
    for label, f, dE, ion in n2_reactions(config):
        k = k_of(f, Te); P += k * dE; parts[f] = (k, k * dE)
        if ion:
            K_ion += k
    return P, K_ion, parts


def rot_bound(Te, kind="ceiling"):
    """Gross rotational power per unit n_e n_N2. 'ceiling': 10 meV/event, sigma held at its table maximum above 10 eV.
    'spectroscopic': NIST level spacings, sigma held at its 10 eV value above 10 eV."""
    E = np.array([r[0] for r in TABLE6]); P = 0.0
    for col in (1, 2):
        s = np.array([r[col] for r in TABLE6]) * 1e-20
        if kind == "ceiling":
            E2 = np.append(E, [np.nextafter(E[-1], np.inf)]); s2 = np.append(s, [s.max()])
            P += maxwellian_rate(E2, s2, Te, "hold") * ROT_DE_CEILING_EV
        else:
            P += maxwellian_rate(E, s, Te, "hold") * ROT_DE_SPECTRO_EV[col]
    return P


def k_n2plus_to_n3plus(Te):
    I, A, B = BELL_N_III
    E = np.concatenate([[I], np.geomspace(I * 1.0001, 1e4, 600)]); x = 1 - I / E
    s = (A * np.log(E / I) + sum(b * x ** (i + 1) for i, b in enumerate(B))) / (I * E) * 1e-17
    return maxwellian_rate(E, np.where(E > I, s, 0.0), Te, "hold")


def main():
    pre = json.load(open(PREREG)); th = pre["thresholds"]
    Tes = [0.2, 0.3, 0.5, 0.7, 1, 1.5, 2, 3, 4, 5, 7.5, 10, 15, 20, 25, 30]
    rows = []
    for Te in Tes:
        P, K_ion, parts = budget(Te)
        k_di, p_di = parts["dissociative_ionization_N2_upper.dat"]
        p_vib = sum(v[1] for f, v in parts.items() if "vib" in f)
        p_rot = rot_bound(Te); k3 = k_n2plus_to_n3plus(Te)
        rows.append(dict(Te_eV=Te, P_total=P, F_P_DI=p_di / P, F_ion_DI=k_di / K_ion, F_P_vib=p_vib / P,
                         F_P_rot_upper=p_rot / (P + p_rot),
                         F_P_rot_spectroscopic=rot_bound(Te, "spectroscopic") / (P + rot_bound(Te, "spectroscopic")),
                         x_crit_N2plus_over_N2_for_1pct_ion=(0.01 / 0.99) * K_ion / k3 if k3 > 0 else None))
    dom = pre["domains"]["default"]["Te_eV"]; vdom = pre["domains"]["vibrational_excitation"]["Te_eV"]
    in_dom = [r for r in rows if dom[0] <= r["Te_eV"] <= dom[1]]; in_v = [r for r in rows if vdom[0] <= r["Te_eV"] <= vdom[1]]
    verdict = {
        "dissociative_ionization": {"final_F_P_max": max(r["F_P_DI"] for r in in_dom), "final_F_ion_max": max(r["F_ion_DI"] for r in in_dom),
                                    "verdict": "PROMOTED (included since 0.4); final fractions on the 0.9 denominator"},
        "vibrational_excitation": {"final_F_P_max": max(r["F_P_vib"] for r in in_v),
                                   "Te_where_F_P_above_1pct": [r["Te_eV"] for r in in_v if r["F_P_vib"] > th["F_P"]],
                                   "verdict": "PROMOTED (included since 0.7); final fractions on the 0.9 denominator; model-form limits unchanged"},
        "rotational_excitation": {"F_P_upper_max": max(r["F_P_rot_upper"] for r in in_v),
                                  "F_P_spectroscopic_max": max(r["F_P_rot_spectroscopic"] for r in in_v),
                                  "Te_where_spectroscopic_above_1pct": [r["Te_eV"] for r in in_v if r["F_P_rot_spectroscopic"] > th["F_P"]],
                                  "reading": "gross loss from j = 0, no superelastic credit (same convention as the vibrational verdict)",
                                  "verdict": "PROMOTE (marginal): spectroscopic gross F_P max 1.13 % at T_e 1-2 eV > 1 %; net loss "
                                             "(detailed balance at kT_gas >> dE) would be far smaller - owner may reverse"},
        "N_Z2plus_to_N_Z3plus": {"x_crit_min": min(r["x_crit_N2plus_over_N2_for_1pct_ion"] for r in in_dom),
                                 "reference_state": REFERENCE_STATE,
                                 "verdict": "EXCLUDED: reference-state n(N^2+)/n(N2) <= 1.2e-3 vs x_crit >= 0.25 (margin ~200); "
                                            "F_ion 4.7e-7, F_S 2.1e-4"},
        "N_to_N_Z2plus_direct": {"verdict": "UNRESOLVED-BY-SOURCE: no cross section in hand; not inferred or scaled"},
        "rule": pre["rule"],
    }
    out = {"audit": "N2 completeness, final pass", "prereg": pre["id"], "reaction_set": "abep-n2n-0.9", "atomic_fraction_x": 0.0,
           "rot_energy_ceiling_eV": ROT_DE_CEILING_EV, "verdict": verdict, "rows": rows}
    json.dump(out, open(OUT, "w"), indent=1, default=float)
    print(json.dumps(verdict, indent=1, default=float))
    print(" T_e   F_P_DI  F_ion_DI  F_P_vib  F_P_rot(ceil)  F_P_rot(spectro)  x_crit(N2+/N2 for 1% F_ion)")
    for r in rows:
        xc = r["x_crit_N2plus_over_N2_for_1pct_ion"]
        print(f" {r['Te_eV']:5.1f}  {r['F_P_DI']:.4f}  {r['F_ion_DI']:.4f}  {r['F_P_vib']:.4f}  {r['F_P_rot_upper']:.2e}      {r['F_P_rot_spectroscopic']:.2e}      "
              f"{xc:.3g}" if xc else " n/a")
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
