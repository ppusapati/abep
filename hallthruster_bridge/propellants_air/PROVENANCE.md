# Hall AIR reaction-set provenance (hallthruster_bridge/propellants_air/)

The Hall AIR_PRIMARY reaction set of the pinned HallThruster.jl v0.23.1, under NP-HALL-CHEM-AIR v1
(`docs/rust_migration/new_physics/NP-HALL-CHEM-AIR/`, lock `1884e42f…`; A9.33 Q2). Label, status and file pins:
`AIR_PINNED.toml`. Loader and guards: `abep_chem::hall_air`. It is separate from the N2/N set (`../propellants/`,
abep-n2n-0.11, never edited here) and from the RF/ICP registry (`data/chemistry/icp/`).

**Status: INCOMPLETE_EVIDENCE. AIR Hall stays NOT_EVALUATED until COMPLETE_FOR_PARAMETRIC_ENVELOPE. That status is not a
validation claim.**

## Reused abep-n2n-0.11 tables (referenced in place)

The 29 files of `../propellants/n2_n.toml`, plus `dissociative_ionization_N2_lower.dat` and `elastic_N_wang2014_bsr.dat`,
are named in the AIR configurations as `../propellants/<file>`. Rules:
- They are sha256-pinned in `AIR_PINNED.toml [reuse]`.
- Their validity entries are mirrored in `rate_validity.toml`. A mirror that differs from the source entry is refused.
- Citations: the `.source` files and `../propellants/PROVENANCE.md`.
- The N2-domain completeness verdicts were made on pure-N2 feeds. Re-assessment on air states: HA-N2N-R1..R3.

## Tables of this set

One row per table. The cross-section representations of rebuilt tables are in `xs/`, extracted unchanged from the v0
DRAFT transcription by `scripts/chemistry/extract_hall_air_xs.py`. The tables are rendered by
`cargo run -p abep-chem --example build_hall_air_tables`, byte-identical to the v0 table they reproduce.

| table | process | role | source | range (eV) | stated uncertainty | validity (mean energy, eV) | status |
|---|---|---|---|---|---|---|---|
| `ionization_O_beb_kd2002.dat` | HA-O-ION-01 | nominal (BEB / Thompson pair) | Kim & Desclaux 2002 BEB via NIST SRD 107 (raw sha256 `76df7f7a…`, not committed); byte-identical copy of the v0 table `1e3a377e…` | 13.618–5000 | none in the table; SONG2026 ≥ 20 % | verified 255 | IN_REPO_VERIFIED |
| `ionization_O_thompson1995.dat` | HA-O-ION-01 | variant (BEB / Thompson pair) | Thompson, Shah & Gilbody 1995 measured points via NIST SRD 107 (raw sha256 `76df7f7a…`); byte-identical copy of the v0 table `a1fe0dcd…`; ramp 13.618 → 14.1 eV assumed | 13.618–2000 | not stated in the table; Thompson / BEB 0.868–1.064 (20–200 eV); NIST column partial vs counting total: verify (VER-HA-03) | verified 255 | IN_REPO_VERIFIED |
| `ionization_O2_song2026.dat` | HA-O2-ION-01 | nominal | SONG2026 Table VII σ(O2⁺) (Straub 1996 via Lindsay & Mangan 2003); accepted manuscript, VoR pending | 13.0–998 | 5 % | verified 255 | IN_REPO_PENDING_VERSION_OF_RECORD |
| `dissociative_ionization_O2_upper_song2026.dat` | HA-O2-DI-01 | nominal (upper) | SONG2026 Table VII σ(O⁺ (+O2²⁺)); ramp from 18.738 eV (inferred D0 + IE); VoR pending | 18.738–998 | 7 % + O⁺ / O2²⁺ ambiguity | verified 255 | IN_REPO_PENDING_VERSION_OF_RECORD |
| `dissociative_ionization_O2_lower_song2026.dat` | HA-O2-DI-01 | variant (lower) | as upper ÷ 1.1 (SONG2026: O2²⁺ ≈ 10 % of the O⁺ signal at 100 eV, applied at every energy; statement-derived) | 18.738–998 | 7 % + ambiguity | verified 255 | IN_REPO_PENDING_VERSION_OF_RECORD |
