# Hall AIR reaction-set provenance (hallthruster_bridge/propellants_air/)

The Hall AIR_PRIMARY reaction set of the pinned HallThruster.jl v0.23.1, under NP-HALL-CHEM-AIR v1
(`docs/rust_migration/new_physics/NP-HALL-CHEM-AIR/`, lock `1884e42f…`; A9.33 Q2). Label, status and file pins:
`AIR_PINNED.toml`. Loader and guards: `abep_chem::hall_air`. It is separate from the N2/N set (`../propellants/`,
abep-n2n-0.11, never edited here) and from the RF/ICP registry (`data/chemistry/icp/`).

**Status: INCOMPLETE_EVIDENCE. AIR Hall stays NOT_EVALUATED until COMPLETE_FOR_PARAMETRIC_ENVELOPE. That status is not a
validation claim.**

## Reused abep-n2n-0.11 tables (referenced in place)

The 27 files of `../propellants/n2_n.toml`, plus `dissociative_ionization_N2_lower.dat` and `elastic_N_wang2014_bsr.dat`,
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
