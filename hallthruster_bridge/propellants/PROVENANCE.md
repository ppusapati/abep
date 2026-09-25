# Rate tables for the N2/N propellant (hallthruster_bridge/propellants/)

Format: HallThruster.jl v0.23.1 rate table. The first line is `<kind> energy (eV): <threshold/loss>` (optional for
elastic), then a column header, then mean electron energy (3/2 T_e) [eV] and Maxwellian rate coefficient [m^3/s].
Integration is done by `abep_sim/rate_tables.py`, which is verified against the closed-form step-cross-section rate.

| file | reaction | cross-section source | status |
|---|---|---|---|
| ionization_N2_N2+.dat | e + N2 -> N2+ + 2e | Itikawa, J. Phys. Chem. Ref. Data 35, 31 (2006); shipped with HallThruster.jl v0.23.1 (MIT) | present |
| elastic_N2.dat | e + N2 momentum transfer | same | present |
| ionization_N.dat | e + N(4S) -> N+ + 2e | Kim & Desclaux, Phys. Rev. A 66, 012708 (2002), BEB ground state, via NIST SRD 107; built by `scripts/build_n_ionization_table.py` (the NIST table is fetched at build time and not committed). Cross-check: the Kim & Desclaux 30 % metastable mix agrees with Brook, Harrison & Smith, J. Phys. B 11, 3115 (1978) to within ~5 % above 17 eV | present (2026-09-25) |
| dissociation_N2.dat | e + N2 -> N + N + e | Cosby, J. Chem. Phys. 98, 9544 (1993), as recommended by Itikawa 2006 / Song et al., JPCRD 52, 023104 (2023) | **missing: source text not accessible from this environment** |
| excitation_N2.dat | e + N2 -> N2* + e (lumped electronic; energy-weighted) | Itikawa 2006 / Song et al. 2023 | **missing: same** |
| elastic_N.dat | e + N momentum transfer | e.g. Wang, Zatsarinny & Bartschat, Phys. Rev. A 89, 062714 (2014) | **missing: same** |

Scope: these files are read only by HallThruster.jl (via `n2_n.toml`). The Python 0-D chemistry (`abep_sim/plasma_chem.py`)
does not read this directory. It uses its own Arrhenius fits except for one table, `abep_sim/data/rates/ionization_N2_N2+.dat`.
The two chemistry databases are **not unified** (a test pins this). The 0-D N-ionization fit is ~2× below `ionization_N.dat`
at T_e = 10 eV.

LXCat is reachable, but its policy doesn't authorise third parties (commercial interests in particular) to redistribute
its data, and commercial inclusion needs written permission from each database owner. So nothing downloaded from LXCat
is committed here; see docs/HISTORY.md (2026-09-25).
