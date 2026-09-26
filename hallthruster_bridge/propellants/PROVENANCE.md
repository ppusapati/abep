# Rate tables for the N2/N propellant (hallthruster_bridge/propellants/)

Format: HallThruster.jl v0.23.1 rate table. The first line is `<label> (eV): <threshold/loss>` (HallThruster.jl parses only the number after the colon; the TOML `energy_eV` key is ignored) (optional for
elastic), then a column header, then mean electron energy (3/2 T_e) [eV] and Maxwellian rate coefficient [m^3/s].
Integration is done by `abep_sim/rate_tables.py`, which is verified against the closed-form step-cross-section rate.

| file | reaction | cross-section source | status |
|---|---|---|---|
| ionization_N2_N2+.dat | e + N2 -> N2+ + 2e | Itikawa, J. Phys. Chem. Ref. Data 35, 31 (2006); shipped with HallThruster.jl v0.23.1 (MIT) | present, **superseded in n2_n.toml by ionization_N2_song2023.dat (abep-n2n-0.2)**; kept for provenance |
| ionization_N2_song2023.dat | e + N2 -> N2+ + 2e (non-dissociative) | Song et al., JPCRD 52, 023104 (2023), Table 10, **partial σ(N₂⁺)** column (Lindsay & Mangan evaluation of Straub 1996 / Rapp & Englander-Golden 1965, ±5 %), 16–1000 eV, transcribed in `scripts/build_n2_ionization_song2023_table.py` (checked row-by-row against the PDF text). The total column is not used: it also counts N⁺+N₂²⁺ and N²⁺, which this reaction does not produce. σ = 0 below 16 eV; held above 1000 eV (tail share 0.96 % at 255 eV). Header 15.58 eV (JPCRD Sec. 3). No 750 eV row in the source | present (2026-09-26), verified to 255 eV |
| elastic_N2.dat | e + N2 momentum transfer | same | present |
| ionization_N.dat | e + N(4S) -> N+ + 2e | Kim & Desclaux, Phys. Rev. A 66, 012708 (2002), BEB ground state, via NIST SRD 107; built by `scripts/build_n_ionization_table.py` (the NIST table is fetched at build time and not committed). Cross-check: the Kim & Desclaux 30 % metastable mix agrees with Brook, Harrison & Smith, J. Phys. B 11, 3115 (1978) to within ~5 % above 17 eV | present (2026-09-25) |
| dissociation_N2.dat | e + N2 -> N + N + e (channel-summed dissociation into neutrals) | Song, Cho, Karwasz, Kokoouline & Tennyson, J. Phys. Chem. Ref. Data 52, 023104 (2023), Table 9: the Cosby, J. Chem. Phys. 98, 9544 (1993) weighted average of Cosby and Winters 1966, ±20 %. Read from the NSF PAR copy (not committed); the 16 values are transcribed in `scripts/build_n2_dissociation_table.py`. σ = 0 below 12 eV (no threshold curve constructed); σ held at the 200 eV value above 200 eV (tail share < 1 % up to 45 eV mean energy, 3.8 % at 60 eV, 14 % at 90 eV: the `.source` file lists it). Header 12.14 eV = N(²D)+N(⁴S) threshold, the dominant channel per Cosby: a **representative fixed energy loss for a channel-summed dissociation cross section, not a universal measured energy loss per dissociation event**. The range 9.75–13.33 eV is a model uncertainty. **Validity domain: mean energy ≤ 45 eV (T_e ≤ 30 eV)**; beyond it the rate rests materially on the held tail | present (2026-09-26) |
| excitation_N2.dat | e + N2 -> N2* + e (lumped electronic; energy-weighted) | Itikawa 2006 / Song et al. 2023 | **missing: same** |
| elastic_N.dat | e + N momentum transfer | e.g. Wang, Zatsarinny & Bartschat, Phys. Rev. A 89, 062714 (2014) | **missing: same** |

Validity domains: `rate_validity.toml` marks each file `verified` (highest mean electron energy at which < 1 % of the
Maxwellian rate rests beyond the last cited cross-section point, capped at HallThruster's 255 eV grid) or `unresolved`.
The driver refuses a reaction set with an unlisted file. A run is `chemistry_trustworthy` only if no file is unresolved
and no reaction has activity (n_e n_target k_r, every saved frame and cell) beyond its limit (schema field).
Audit 2026-09-26: `ionization_N.dat` verified to 255 eV (NIST source 15–5000 eV; tail share 0.0000 %). The shipped
`ionization_N2_N2+.dat` (0–300 eV) and `elastic_N2.dat` (0–100 eV only; the solver holds the 100 eV value above) are
unresolved: HallThruster.jl ships the rate tables but not the Itikawa 2006 cross-section inputs, so their tails cannot be
audited. Rebuilding them from Song et al. JPCRD 2023 Table 10 (ionization) and Table 5 (MTCS, 0.001 eV–10 keV) would
resolve both.

Scope: these files are read only by HallThruster.jl (via `n2_n.toml`). The Python 0-D chemistry (`abep_sim/plasma_chem.py`)
does not read this directory. It uses its own Arrhenius fits except for one table, `abep_sim/data/rates/ionization_N2_N2+.dat`.
The two chemistry databases are **not unified** (a test pins this). The 0-D N-ionization fit is ~2× below `ionization_N.dat`
at T_e = 10 eV.

LXCat is reachable, but its policy doesn't authorise third parties (commercial interests in particular) to redistribute
its data, and commercial inclusion needs written permission from each database owner. So nothing downloaded from LXCat
is committed here; see docs/HISTORY.md (2026-09-25).
