"""Regenerate the chemistry-variant propellant configs from hallthruster_bridge/propellants/n2_n.toml, so a variant can
never drift from the nominal set. Each variant differs from n2_n.toml in exactly the listed rate files (tested).
  n2_n_di_lower.toml: dissociative ionization lower variant (N+ + N2++ column minus the ~1 % N2++ share).
  n2_n_nel_wang.toml: atomic-N momentum transfer from Wang et al. 2014 BSR (via Ragimkhanov Fig. 1b) instead of OPM.
  n2_n_di_lower_nel_wang.toml: both.
  n2_n_rot_off.toml: the two rotational reactions removed (lower-bound closure for rotational cooling).
  n2_n_exc_johnsonlow.toml: electronic excitation from Johnson 2005 at all energies (sensitivity branch; escalation rule in the
    P5-N2 pre-registration).
  Escalation combinations (ESCALATION below): every staged sensitivity x the other primary chemistry combinations.
  n2_n_ndd_hmslow.toml / n2_n_ndd_hmshigh.toml: direct N -> N^2+ (Hahn, Muller & Savin 2017) x0.5 / x1.3 (sensitivity branches).
  n2_n_n2dication.toml: molecular N2^2+ UNCERTAINTY VARIANT (closure verdict: nominal < 1 % < upper): N2 max_charge = 2,
    N2 + e -> N2^2+ + 3e (upper envelope) and N2+ + e -> N2^2+ + 2e (Tabata 2006 n2-69), on the dissociative-ionization LOWER
    table (the N+ + N2++ column minus its ~1 % N2++ share), so that N2^2+ is not counted twice.
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
NDD = 'rate_coeff_file = "ionization_N_to_N_Z2plus_hms2017.dat"          # Hahn, Muller & Savin 2017 Eqs. (2)+(3), direct N -> N^2+ (abep-n2n-0.11); sensitivity x0.5 / x1.3: n2_n_ndd_hmslow/high.toml'
NDD_LOW = {NDD: 'rate_coeff_file = "ionization_N_to_N_Z2plus_hms2017_x0p5.dat"     # HMS 2017 x 0.5: direct N -> N^2+ SENSITIVITY branch (abep-n2n-0.11)'}
NDD_HIGH = {NDD: 'rate_coeff_file = "ionization_N_to_N_Z2plus_hms2017_x1p3.dat"     # HMS 2017 x 1.3: direct N -> N^2+ SENSITIVITY branch (abep-n2n-0.11)'}
N2_DICATION = {
    """symbol = "N2"
name = "Molecular Nitrogen"
max_charge = 1""": """symbol = "N2"
name = "Molecular Nitrogen"
max_charge = 2                                      # molecular N2^2+ UNCERTAINTY VARIANT (abep-n2n-0.11)""",
    NDD: NDD + """

[[reactions]]
type = "electron_impact"
equation = "N2 + e -> N2(2+) + 3e"
rate_coeff_file = "ionization_N2_to_N2_Z2plus_upper.dat"           # all double ionization 0.14e-16 cm^2 from 42.9 eV: N2^2+ UNCERTAINTY VARIANT (abep-n2n-0.11)

[[reactions]]
type = "electron_impact"
equation = "N2(+) + e -> N2(2+) + 2e"
rate_coeff_file = "ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.dat"  # Tabata 2006 n2-69 fit to Bahati 2001: N2^2+ UNCERTAINTY VARIANT (abep-n2n-0.11)""",
    **DI_LOWER}
VARIANTS = {"n2_n_di_lower.toml": ("dissociative-ionization LOWER chemistry variant", DI_LOWER),
            "n2_n_nel_wang.toml": ("atomic-N momentum-transfer WANG-BSR chemistry variant", NEL_WANG),
            "n2_n_di_lower_nel_wang.toml": ("dissociative-ionization LOWER x atomic-N momentum-transfer WANG-BSR variant",
                                            {**DI_LOWER, **NEL_WANG}),
            "n2_n_exc_johnsonlow.toml": ("electronic-excitation JOHNSON-LOW sensitivity branch (nominal DI, OPM N elastic)",
                                         EXC_JOHNSONLOW),
            "n2_n_ndd_hmslow.toml": ("direct N -> N^2+ HMS x0.5 sensitivity branch (nominal DI, OPM N elastic)", NDD_LOW),
            "n2_n_ndd_hmshigh.toml": ("direct N -> N^2+ HMS x1.3 sensitivity branch (nominal DI, OPM N elastic)", NDD_HIGH),
            "n2_n_n2dication.toml": ("molecular N2^2+ UNCERTAINTY VARIANT (DI lower, OPM N elastic)", N2_DICATION),
            "n2_n_rot_off.toml": ("rotational-OFF lower-bound closure (gross rotational cooling removed; nominal DI, OPM N elastic)",
                                  ROT_OFF)}

# Escalation combinations of the staged sensitivities (pre-registered with p5_n2_validation_criteria_v1, PR #27 review): each
# nominal-base sensitivity x the other three primary chemistry combinations, generated and hash-pinned BEFORE any run so that an
# escalation never needs chemistry defined after results are seen. The molecular-N2^2+ branch is defined only on DI-lower (the
# DI-upper table already counts N2^2+ as N+), so its baseline is n2_n_di_lower.toml and its only escalation is x Wang elastic.
PRIMARY_COMBOS = {"di_lower": ("DI lower", DI_LOWER), "nel_wang": ("Wang-BSR N elastic", NEL_WANG),
                  "di_lower_nel_wang": ("DI lower x Wang-BSR N elastic", {**DI_LOWER, **NEL_WANG})}
STAGED = {"n2_n_exc_johnsonlow": ("electronic-excitation JOHNSON-LOW", EXC_JOHNSONLOW), "n2_n_rot_off": ("rotational-OFF", ROT_OFF),
          "n2_n_ndd_hmslow": ("direct N -> N^2+ HMS x0.5", NDD_LOW), "n2_n_ndd_hmshigh": ("direct N -> N^2+ HMS x1.3", NDD_HIGH)}
ESCALATION = {}
for stem, (what, subs) in STAGED.items():
    for tag, (cwhat, csubs) in PRIMARY_COMBOS.items():
        ESCALATION[f"{stem}_{tag}.toml"] = (f"{what} sensitivity x {cwhat} (escalation combination)", {**subs, **csubs})
ESCALATION["n2_n_n2dication_nel_wang.toml"] = ("molecular N2^2+ UNCERTAINTY VARIANT x Wang-BSR N elastic (escalation combination; "
                                               "DI lower)", {**N2_DICATION, **NEL_WANG})
VARIANTS.update(ESCALATION)


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
