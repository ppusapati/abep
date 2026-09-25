# Cross-section-derived rate tables (authoritative where present)

| file | reaction | source | licence |
|---|---|---|---|
| ionization_N2_N2+.dat | e + N2 -> N2+ + 2e | Itikawa Y., J. Phys. Chem. Ref. Data 35(1), 31 (2006), Maxwellian-integrated; copied from HallThruster.jl v0.23.1 (commit bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5), reactions/ | MIT (HallThruster.jl) |
| elastic_N2.dat | e + N2 momentum transfer | same | MIT |

Energy column = mean electron energy = 3/2 T_e (HallThruster.jl convention, docs/src/reference/collisions.md).
Finding (2026-09-25): the previous Arrhenius fit for N2 ionisation in plasma_chem.RATES was 2.2-3.2x LOW versus this table
over T_e = 3-200 eV. All other reactions (O, O2, N ionisation; O2/N2 dissociation; dissociative ionisation; excitation)
remain literature-class fits and are UNVERIFIED until cross sections (LXCat: Itikawa/Phelps/IST-Lisbon sets) are integrated.
