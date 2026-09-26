"""Build the N2 vibrational-excitation tables excitation_N2_vib_0_to_<vf>.dat, v_f = 1..10 (reaction set abep-n2n-0.7),
promoted by audit 2 (hallthruster_bridge/audit/n2_vibrational_excitation_v1.json).

Rates: Laporta, Little, Celiberto & Tennyson, Plasma Sources Sci. Technol. 23, 065002 (2014), Eq. (10) fits of the
Maxwellian rate coefficients for resonant (2Pi_g) excitation e + N2(v=0) -> e + N2(v_f):
    k_{0->vf}(T_e) = kappa_max (T_max / T_e)^(3/2) exp(-T_max / T_e),   kappa_max in 1e-9 cm^3/s, T in eV
with (T_max, kappa_max) and the level energies eps_v transcribed in scripts/audit_n2_vibrational_excitation.py
(LAPORTA_V0, EPS_V; Laporta supplementary file and Table II). These are fitted RATE coefficients, not cross sections:
nothing is integrated here. HallThruster.jl indexes rate tables by mean electron energy eps_bar = 3/2 T_e, so each
table row eps_bar holds Laporta evaluated at T_e = (2/3) eps_bar (regression-tested).
Header energy loss = eps_vf - eps_0 (Laporta Table II; eps_0 = 0 by construction).

Cutoff v_f <= 10 is a result, not a choice: the omitted tail v_f = 11..58 carries at most 0.145 % of the vibrational
power anywhere in T_e = 0.2-30 eV (vib_tail_fraction(); printed), hence < 0.145 % of P_e, below the pre-registered 1 %.

Closure limitations (carried as a defined closure uncertainty for P5-N2; NOT a complete vibrational kinetics model):
  * HallThruster.jl does not track vibrational populations: every N2 is taken in v = 0, so there is no stepwise
    v_i > 0 excitation and no superelastic (de-excitation) return; the model represents gross electron cooling.
  * Resonant excitation only (Laporta cross sections integrated to 15 eV); non-resonant excitation is absent.
  * Validity domain: Laporta do not state a validated temperature range for the RVE fits (their Fig. 5b shows the
    calculated rates to 50,000 K = 4.31 eV); see rate_validity.toml and docs/HISTORY.md for the limit carried.
Usage: python scripts/build_n2_vibrational_tables.py
"""
import importlib.util, os, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
_spec = importlib.util.spec_from_file_location("vib", os.path.join(os.path.dirname(__file__), "audit_n2_vibrational_excitation.py"))
vib = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(vib)

PROP = os.path.join(ROOT, "hallthruster_bridge", "propellants")
VF_MAX = 10
EPS_BAR_MAX = 300.0


def fname(vf):
    return f"excitation_N2_vib_0_to_{vf}.dat"


def k_table(vf, eps_bar):
    """Rate [m^3/s] on HallThruster's axis: eps_bar = 3/2 T_e -> Laporta evaluated at T_e = 2/3 eps_bar."""
    Te = 2.0 * eps_bar / 3.0
    return vib.k_vib(Te, vf)[0][1] if Te > 0 else 0.0


def vib_tail_fraction(Te, vf_max=VF_MAX):
    ks = vib.k_vib(Te); P = [k * vib.EPS_V[v] for v, k in ks]
    return sum(p for (v, _), p in zip(ks, P) if v > vf_max) / sum(P)


def main():
    Tes = [0.2, 0.3, 0.5, 0.7, 1, 1.5, 2, 3, 4, 5, 7.5, 10, 15, 20, 25, 30]
    worst = max(vib_tail_fraction(T) for T in Tes)
    print(f"omitted v_f > {VF_MAX} share of vibrational power, max over T_e 0.2-30 eV: {100 * worst:.4f} %")
    assert worst < 0.01
    for vf in range(1, VF_MAX + 1):
        dE = vib.EPS_V[vf] - vib.EPS_V[0]
        path = os.path.join(PROP, fname(vf))
        with open(path, "w") as f:
            f.write(f"Excitation energy (eV): {dE}\n")
            f.write("Energy (eV)\tRate coefficient (m^3/s)\n")
            for eps in np.arange(0.0, EPS_BAR_MAX + 1.0, 1.0):
                f.write(f"{eps:.1f}\t{k_table(vf, eps):.6e}\n")
        with open(path + ".source", "w") as f:
            f.write(f"e + N2(v=0) -> e + N2(v={vf}) resonant vibrational excitation. Rate: Laporta et al., Plasma Sources Sci. "
                    f"Technol. 23, 065002 (2014), Eq. (10) fit, supplementary v_i = 0 -> v_f = {vf} (T_max, kappa_max), evaluated at "
                    "T_e = (2/3) x table energy (mean electron energy). Header = eps_vf (Laporta Table II). v = 0 only, no "
                    "superelastic return, resonant only (see scripts/build_n2_vibrational_tables.py). Reaction set abep-n2n-0.7.\n")
        print("wrote", fname(vf), f"dE = {dE} eV")


if __name__ == "__main__":
    main()
