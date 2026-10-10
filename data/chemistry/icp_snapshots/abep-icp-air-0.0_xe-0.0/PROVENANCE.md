# ICP chemistry registry provenance (data/chemistry/icp/)

Registry of the active RF/ICP neutralizer chemistry: NP-ICP-CHEM-AIR v1 (`docs/rust_migration/new_physics/NP-ICP-CHEM-AIR/`,
lock `f42c2269…`), interface IF-CHEM-REG-v1 (provider `abep-chem`, consumer `abep-icp`). Labels and file pins:
`ICP_CHEM_PINNED.toml`. Separate from the Hall chemistry (`hallthruster_bridge/PINNED.toml`, abep-n2n-0.11), which no
ICP chemistry commit edits (FC-CHEM-10).

**BP-S1 (abep-icp-air-0.0 / abep-icp-xe-0.0): no new table.** The 43 abep-n2n-0.11 tables are reused by reference
(`reuse_pins.json`, path + sha256; their citations are the `.source` files and `hallthruster_bridge/propellants/PROVENANCE.md`).
Their validity entries are mirrored in `rate_validity_icp.toml`. The O/O2 v0 DRAFT files are pinned only; they have no
channel until BP-S2 / BP-S4. No Xe data exist.

**Direct-rate representations (`xs/`).** EQ-06 / IX-01 evaluate each rate as the Maxwellian integral of the registered
cross-section representation (abep-chem integrator, contract C-ABEP_SIM_RATE_TABLES_PY, admitted); the `.dat` is a
cross-check (NV-06 / UQ-06). For 32 reused tables the representation is the cross-section point list each
`scripts/build_*.py` passes to `rate_tables.write_hallthruster_table`, extracted without change from the parity capture
`docs/rust_migration/contracts/C-ABEP_SIM_RATE_TABLES_PY/reference_outputs/inputs.json.gz` (sha256 `a2c811bf…`) by
`crates/abep-chem/examples/build_icp_xs.rs`. The Python reference (contract INV-02) and the admitted Rust port render the
frozen `.dat` from those points byte for byte; each xs file records the capture id, builder script and both sha256.
Two kinds of reused table have no registered representation, so they give no direct rate (INCOMPLETE_EVIDENCE):

- `ionization_N.dat`: the NIST SRD 107 Kim & Desclaux table is fetched at build time and not committed.
- `excitation_N2_vib_0_to_{1..10}.dat`: Laporta et al. 2014 rate fits; no registered fit-parameter file and no admitted
  rate-fit evaluator.

| channel | table (reused) | representation | validity (mean energy, eV) | role |
|---|---|---|---|---|
| AIR-ION-03/ionization_N2_song2023 | `ionization_N2_song2023.dat` | `xs/ionization_N2_song2023.json` | verified 255.0 | NOMINAL |
| AIR-ION-04/ionization_N | `ionization_N.dat` | none: NIST table not committed | verified 255.0 | NOMINAL |
| AIR-ION-06/dissociative_ionization_N2_upper | `dissociative_ionization_N2_upper.dat` | `xs/dissociative_ionization_N2_upper.json` | verified 255.0 | NOMINAL (DI) |
| AIR-ION-06/dissociative_ionization_N2_lower | `dissociative_ionization_N2_lower.dat` | `xs/dissociative_ionization_N2_lower.json` | verified 255.0 | VARIANT (DI) |
| AIR-ION-07/dissociative_ionization_N2_to_N_Z2plus | `dissociative_ionization_N2_to_N_Z2plus.dat` | `xs/dissociative_ionization_N2_to_N_Z2plus.json` | verified 255.0 | NOMINAL |
| AIR-ION-08/ionization_N_to_N_Z2plus_hms2017 | `ionization_N_to_N_Z2plus_hms2017.dat` | `xs/ionization_N_to_N_Z2plus_hms2017.json` | verified 255.0 | NOMINAL (HMS) |
| AIR-ION-08/ionization_N_to_N_Z2plus_hms2017_x0p5 | `ionization_N_to_N_Z2plus_hms2017_x0p5.dat` | `xs/ionization_N_to_N_Z2plus_hms2017_x0p5.json` | verified 255.0 | SENSITIVITY (HMS) |
| AIR-ION-08/ionization_N_to_N_Z2plus_hms2017_x1p3 | `ionization_N_to_N_Z2plus_hms2017_x1p3.dat` | `xs/ionization_N_to_N_Z2plus_hms2017_x1p3.json` | verified 255.0 | SENSITIVITY (HMS) |
| AIR-ION-09/ionization_N_Z1plus_to_N_Z2plus | `ionization_N_Z1plus_to_N_Z2plus.dat` | `xs/ionization_N_Z1plus_to_N_Z2plus.json` | verified 255.0 | NOMINAL |
| AIR-ION-10/ionization_N2_to_N2_Z2plus_upper | `ionization_N2_to_N2_Z2plus_upper.dat` | `xs/ionization_N2_to_N2_Z2plus_upper.json` | verified 255.0 | UNCERTAINTY_VARIANT (N2_DICATION) |
| AIR-ION-10/ionization_N2_Z1plus_to_N2_Z2plus_tabata2006 | `ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.dat` | `xs/ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.json` | verified 255.0 | UNCERTAINTY_VARIANT (N2_DICATION) |
| AIR-DIS-01/dissociation_N2 | `dissociation_N2.dat` | `xs/dissociation_N2.json` | verified 45.0 | NOMINAL |
| AIR-EXC-01/excitation_N2_A3Sigma_u | `excitation_N2_A3Sigma_u.dat` | `xs/excitation_N2_A3Sigma_u.json` | verified 45.0 | NOMINAL (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_B3Pi_g | `excitation_N2_B3Pi_g.dat` | `xs/excitation_N2_B3Pi_g.json` | verified 45.0 | NOMINAL (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_W3Delta_u | `excitation_N2_W3Delta_u.dat` | `xs/excitation_N2_W3Delta_u.json` | verified 45.0 | NOMINAL (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_Bprime3Sigma_u | `excitation_N2_Bprime3Sigma_u.dat` | `xs/excitation_N2_Bprime3Sigma_u.json` | verified 45.0 | NOMINAL (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_a1Pi_g | `excitation_N2_a1Pi_g.dat` | `xs/excitation_N2_a1Pi_g.json` | verified 45.0 | NOMINAL (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_aprime1Sigma_u | `excitation_N2_aprime1Sigma_u.dat` | `xs/excitation_N2_aprime1Sigma_u.json` | verified 45.0 | NOMINAL (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_w1Delta_u | `excitation_N2_w1Delta_u.dat` | `xs/excitation_N2_w1Delta_u.json` | verified 45.0 | NOMINAL (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_C3Pi_u | `excitation_N2_C3Pi_u.dat` | `xs/excitation_N2_C3Pi_u.json` | verified 45.0 | NOMINAL (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_A3Sigma_u_johnsonlow | `excitation_N2_A3Sigma_u_johnsonlow.dat` | `xs/excitation_N2_A3Sigma_u_johnsonlow.json` | verified 45.0 | SENSITIVITY (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_B3Pi_g_johnsonlow | `excitation_N2_B3Pi_g_johnsonlow.dat` | `xs/excitation_N2_B3Pi_g_johnsonlow.json` | verified 45.0 | SENSITIVITY (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_W3Delta_u_johnsonlow | `excitation_N2_W3Delta_u_johnsonlow.dat` | `xs/excitation_N2_W3Delta_u_johnsonlow.json` | verified 45.0 | SENSITIVITY (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_Bprime3Sigma_u_johnsonlow | `excitation_N2_Bprime3Sigma_u_johnsonlow.dat` | `xs/excitation_N2_Bprime3Sigma_u_johnsonlow.json` | verified 45.0 | SENSITIVITY (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_a1Pi_g_johnsonlow | `excitation_N2_a1Pi_g_johnsonlow.dat` | `xs/excitation_N2_a1Pi_g_johnsonlow.json` | verified 45.0 | SENSITIVITY (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_aprime1Sigma_u_johnsonlow | `excitation_N2_aprime1Sigma_u_johnsonlow.dat` | `xs/excitation_N2_aprime1Sigma_u_johnsonlow.json` | verified 45.0 | SENSITIVITY (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_w1Delta_u_johnsonlow | `excitation_N2_w1Delta_u_johnsonlow.dat` | `xs/excitation_N2_w1Delta_u_johnsonlow.json` | verified 45.0 | SENSITIVITY (EXC_JOHNSONLOW) |
| AIR-EXC-01/excitation_N2_C3Pi_u_johnsonlow | `excitation_N2_C3Pi_u_johnsonlow.dat` | `xs/excitation_N2_C3Pi_u_johnsonlow.json` | verified 45.0 | SENSITIVITY (EXC_JOHNSONLOW) |
| AIR-EXC-02/excitation_N2_vib_0_to_1 | `excitation_N2_vib_0_to_1.dat` | none: rate fit, not registered | verified 45.0 | NOMINAL |
| AIR-EXC-02/excitation_N2_vib_0_to_2 | `excitation_N2_vib_0_to_2.dat` | none: rate fit, not registered | verified 45.0 | NOMINAL |
| AIR-EXC-02/excitation_N2_vib_0_to_3 | `excitation_N2_vib_0_to_3.dat` | none: rate fit, not registered | verified 45.0 | NOMINAL |
| AIR-EXC-02/excitation_N2_vib_0_to_4 | `excitation_N2_vib_0_to_4.dat` | none: rate fit, not registered | verified 45.0 | NOMINAL |
| AIR-EXC-02/excitation_N2_vib_0_to_5 | `excitation_N2_vib_0_to_5.dat` | none: rate fit, not registered | verified 45.0 | NOMINAL |
| AIR-EXC-02/excitation_N2_vib_0_to_6 | `excitation_N2_vib_0_to_6.dat` | none: rate fit, not registered | verified 45.0 | NOMINAL |
| AIR-EXC-02/excitation_N2_vib_0_to_7 | `excitation_N2_vib_0_to_7.dat` | none: rate fit, not registered | verified 45.0 | NOMINAL |
| AIR-EXC-02/excitation_N2_vib_0_to_8 | `excitation_N2_vib_0_to_8.dat` | none: rate fit, not registered | verified 45.0 | NOMINAL |
| AIR-EXC-02/excitation_N2_vib_0_to_9 | `excitation_N2_vib_0_to_9.dat` | none: rate fit, not registered | verified 45.0 | NOMINAL |
| AIR-EXC-02/excitation_N2_vib_0_to_10 | `excitation_N2_vib_0_to_10.dat` | none: rate fit, not registered | verified 45.0 | NOMINAL |
| AIR-EXC-03/excitation_N2_rot_j0_to_j2 | `excitation_N2_rot_j0_to_j2.dat` | `xs/excitation_N2_rot_j0_to_j2.json` | verified 45.0 | NOMINAL (ROT_OFF) |
| AIR-EXC-03/excitation_N2_rot_j0_to_j4 | `excitation_N2_rot_j0_to_j4.dat` | `xs/excitation_N2_rot_j0_to_j4.json` | verified 45.0 | NOMINAL (ROT_OFF) |
| AIR-EL-01/elastic_N2_song2023 | `elastic_N2_song2023.dat` | `xs/elastic_N2_song2023.json` | verified 255.0 | NOMINAL |
| AIR-EL-02/elastic_N_ragimkhanov2026 | `elastic_N_ragimkhanov2026.dat` | `xs/elastic_N_ragimkhanov2026.json` | verified 255.0 | NOMINAL (N_ELASTIC) |
| AIR-EL-02/elastic_N_wang2014_bsr | `elastic_N_wang2014_bsr.dat` | `xs/elastic_N_wang2014_bsr.json` | verified 255.0 | VARIANT (N_ELASTIC) |

