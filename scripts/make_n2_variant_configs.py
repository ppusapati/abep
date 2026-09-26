"""Regenerate the chemistry-variant propellant configs from hallthruster_bridge/propellants/n2_n.toml, so a variant can
never drift from the nominal set. Each variant differs from n2_n.toml in exactly the listed rate files (tested).
  n2_n_di_lower.toml: dissociative ionization lower variant (N+ + N2++ column minus the ~1 % N2++ share).
Usage: python scripts/make_n2_variant_configs.py
"""
import os

PROP = os.path.join(os.path.dirname(__file__), "..", "hallthruster_bridge", "propellants")
VARIANTS = {"n2_n_di_lower.toml": ("dissociative-ionization LOWER chemistry variant",
                                   {'rate_coeff_file = "dissociative_ionization_N2_upper.dat"  # Song 2023 Table 10 sigma(N+ + N2++), upper variant (abep-n2n-0.4); lower variant: n2_n_di_lower.toml':
                                    'rate_coeff_file = "dissociative_ionization_N2_lower.dat"  # Song 2023 Table 10 sigma(N+ + N2++) - 0.01 sigma_total, LOWER variant (abep-n2n-0.4)'})}


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
