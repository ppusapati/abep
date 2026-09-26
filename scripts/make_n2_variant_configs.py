"""Regenerate the chemistry-variant propellant configs from hallthruster_bridge/propellants/n2_n.toml, so a variant can
never drift from the nominal set. Each variant differs from n2_n.toml in exactly the listed rate files (tested).
  n2_n_di_lower.toml: dissociative ionization lower variant (N+ + N2++ column minus the ~1 % N2++ share).
  n2_n_nel_wang.toml: atomic-N momentum transfer from Wang et al. 2014 BSR (via Ragimkhanov Fig. 1b) instead of OPM.
  n2_n_di_lower_nel_wang.toml: both.
  n2_n_rot_off.toml: the two rotational reactions removed (lower-bound closure for rotational cooling).
  n2_n_exc_johnsonlow.toml: electronic excitation from Johnson 2005 at all energies (sensitivity branch; escalation rule in the
    P5-N2 pre-registration).
Usage: python scripts/make_n2_variant_configs.py
"""
import os

PROP = os.path.join(os.path.dirname(__file__), "..", "hallthruster_bridge", "propellants")
DI_LOWER = {'rate_coeff_file = "dissociative_ionization_N2_upper.dat"  # Song 2023 Table 10 sigma(N+ + N2++), upper variant (abep-n2n-0.4); lower variant: n2_n_di_lower.toml':
            'rate_coeff_file = "dissociative_ionization_N2_lower.dat"  # Song 2023 Table 10 sigma(N+ + N2++) - 0.01 sigma_total, LOWER variant (abep-n2n-0.4)'}
NEL_WANG = {'rate_coeff_file = "elastic_N_ragimkhanov2026.dat"    # Ragimkhanov et al. EPJD 2026 Fig. 1b OPM MTCS (abep-n2n-0.8); Wang BSR variant: n2_n_nel_wang.toml':
            'rate_coeff_file = "elastic_N_wang2014_bsr.dat"        # Wang et al. 2014 BSR MTCS via Ragimkhanov Fig. 1b, OPM above 128 eV: N-elastic VARIANT (abep-n2n-0.8)'}
EXC_JOHNSONLOW = {'rate_coeff_file = "excitation_N2_A3Sigma_u.dat"   # Su 2021 (<20 eV) + Johnson 2005 (>=20 eV), dE = 7.75 eV (abep-n2n-0.9)': 'rate_coeff_file = "excitation_N2_A3Sigma_u_johnsonlow.dat"   # JOHNSON-LOW sensitivity branch (Johnson 2005 at all energies)', 'rate_coeff_file = "excitation_N2_B3Pi_g.dat"   # Su 2021 (<20 eV) + Johnson 2005 (>=20 eV), dE = 8.04 eV (abep-n2n-0.9)': 'rate_coeff_file = "excitation_N2_B3Pi_g_johnsonlow.dat"   # JOHNSON-LOW sensitivity branch (Johnson 2005 at all energies)', 'rate_coeff_file = "excitation_N2_W3Delta_u.dat"   # Su 2021 (<20 eV) + Johnson 2005 (>=20 eV), dE = 8.88 eV (abep-n2n-0.9)': 'rate_coeff_file = "excitation_N2_W3Delta_u_johnsonlow.dat"   # JOHNSON-LOW sensitivity branch (Johnson 2005 at all energies)', 'rate_coeff_file = "excitation_N2_Bprime3Sigma_u.dat"   # Su 2021 (<20 eV) + Johnson 2005 (>=20 eV), dE = 9.67 eV (abep-n2n-0.9)': 'rate_coeff_file = "excitation_N2_Bprime3Sigma_u_johnsonlow.dat"   # JOHNSON-LOW sensitivity branch (Johnson 2005 at all energies)', 'rate_coeff_file = "excitation_N2_a1Pi_g.dat"   # Su 2021 (<20 eV) + Johnson 2005 (>=20 eV), dE = 9.31 eV (abep-n2n-0.9)': 'rate_coeff_file = "excitation_N2_a1Pi_g_johnsonlow.dat"   # JOHNSON-LOW sensitivity branch (Johnson 2005 at all energies)', 'rate_coeff_file = "excitation_N2_aprime1Sigma_u.dat"   # Su 2021 (<20 eV) + Johnson 2005 (>=20 eV), dE = 9.92 eV (abep-n2n-0.9)': 'rate_coeff_file = "excitation_N2_aprime1Sigma_u_johnsonlow.dat"   # JOHNSON-LOW sensitivity branch (Johnson 2005 at all energies)', 'rate_coeff_file = "excitation_N2_w1Delta_u.dat"   # Su 2021 (<20 eV) + Johnson 2005 (>=20 eV), dE = 10.27 eV (abep-n2n-0.9)': 'rate_coeff_file = "excitation_N2_w1Delta_u_johnsonlow.dat"   # JOHNSON-LOW sensitivity branch (Johnson 2005 at all energies)', 'rate_coeff_file = "excitation_N2_C3Pi_u.dat"   # Su 2021 (<20 eV) + Johnson 2005 (>=20 eV), dE = 11.19 eV (abep-n2n-0.9)': 'rate_coeff_file = "excitation_N2_C3Pi_u_johnsonlow.dat"   # JOHNSON-LOW sensitivity branch (Johnson 2005 at all energies)'}
ROT_OFF = {"""[[reactions]]
type = "excitation"
target_species = "N2"
rate_coeff_file = "excitation_N2_rot_j0_to_j2.dat"      # JPCRD 2023 Table 6, dE = 6 B_0 = 1.480 meV (abep-n2n-0.10)

[[reactions]]
type = "excitation"
target_species = "N2"
rate_coeff_file = "excitation_N2_rot_j0_to_j4.dat"      # JPCRD 2023 Table 6, dE = 20 B_0 = 4.933 meV (abep-n2n-0.10)

""": ""}
VARIANTS = {"n2_n_di_lower.toml": ("dissociative-ionization LOWER chemistry variant", DI_LOWER),
            "n2_n_nel_wang.toml": ("atomic-N momentum-transfer WANG-BSR chemistry variant", NEL_WANG),
            "n2_n_di_lower_nel_wang.toml": ("dissociative-ionization LOWER x atomic-N momentum-transfer WANG-BSR variant",
                                            {**DI_LOWER, **NEL_WANG}),
            "n2_n_exc_johnsonlow.toml": ("electronic-excitation JOHNSON-LOW sensitivity branch (nominal DI, OPM N elastic)",
                                         EXC_JOHNSONLOW),
            "n2_n_rot_off.toml": ("rotational-OFF lower-bound closure (gross rotational cooling removed; nominal DI, OPM N elastic)",
                                  ROT_OFF)}


def main():
    base = open(os.path.join(PROP, "n2_n.toml")).read()
    for name, (what, subs) in VARIANTS.items():
        s = base
        for a, b in subs.items():
            assert s.count(a) == 1, a
            s = s.replace(a, b)
        s = f"# GENERATED VARIANT of n2_n.toml ({what}) by scripts/make_n2_variant_configs.py; do not edit by hand.\n" + s
        open(os.path.join(PROP, name), "w").write(s)
        print("wrote", name)


if __name__ == "__main__":
    main()
