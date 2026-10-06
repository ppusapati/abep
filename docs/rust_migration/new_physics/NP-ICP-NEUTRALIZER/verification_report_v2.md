# NP-ICP-NEUTRALIZER v1 — verification report v2

| item | value |
|---|---|
| model | `NP-ICP-NEUTRALIZER`, model_version `1` (NEW_PHYSICS; no Python reference; nothing from `plasma_chem.py`) |
| contract | `prereg_v1.json` `5d496ea6…` + `PREREG.md` `3af97940…` (lock `e98747e0…`), addenda `01_a9_30` `f8e12249…` and `02_chem_air` `7c1dd1f7…`; chemistry contract NP-ICP-CHEM-AIR v1 (lock `f42c2269…`), interface IF-CHEM-REG-v1 |
| previous report | `verification_report_v1.json` `11ddb2a2…` / `.md` `80bf66d2…`: immutable, not edited; every v1 result not listed here stands |
| implementation | `crates/abep-icp` + `crates/abep-chem` (`registry`, `checked`) + `data/chemistry/icp/`; commits `f430d7b` (BP-S1 registry), `e404c15` (EQ-06 wiring); base `def19d6` |
| chemistry registry | `ICP_CHEM_PINNED.toml` `074daff9…`, labels `abep-icp-air-0.0` / `abep-icp-xe-0.0` (both NOT_ADMITTED) |
| toolchain | rustc / cargo 1.94.1 |
| tests | abep-icp 63, abep-chem 40; workspace 326 passed, 0 failed, 2 ignored (PT-01 / PT-02, the registered Julia platform tests of abep-julia-bridge); `cargo fmt -- --check`, clippy `-D warnings` clean |
| **verification status** | **`IMPLEMENTED_UNVERIFIED`** (unchanged). Admission-rule items 4 and 5 are open. |
| **validation status** | **`NOT_VALIDATED`** on every output |
| machine-readable | `verification_report_v2.json` (authoritative; numbers from `cargo run -p abep-icp --example verification_table --locked`, output `776c9d67…`, two runs byte-identical) |

## What changed since v1

- **BP-S1 registry.** `data/chemistry/icp/` exists as the NP-ICP-CHEM-AIR build plan defines it. It lists every contract
  process with the status the contract records (AIR 15 / 16 / 23, XE 1 / 5 / 4). It has 43 channels for the reused
  abep-n2n-0.11 tables, each with its path + sha256 and a mirrored validity entry, and the FC-CHEM-10 Hall-isolation check.
  No new table was built and no file under `hallthruster_bridge/` was touched.
- **Direct-rate representations.** 32 of the 43 reused tables carry their cross-section points in `xs/`. They are
  extracted unchanged from the committed C-ABEP_SIM_RATE_TABLES_PY v1 capture. Both the Python reference and the
  admitted Rust port render each frozen `.dat` byte for byte from these points; this lane re-checked three tables.
  Two kinds of table have no representation:
  - `ionization_N.dat`: the NIST table is not committed;
  - the 10 vibrational rate fits: there is no fit-parameter file and no admitted rate-fit evaluator.
- **EQ-06.** A registered table's rate is `abep_chem::checked::maxwellian_rate` on its registered representation. This
  holds in the solve and in NV-06. No rate is computed in abep-icp.
  - The v1 gate `EQ-06_ABEP_CHEM_INTEGRATOR_NOT_ADMITTED` now reads the sha256-pinned admission record (ADMITTED /
    PARITY_PASS), so it no longer fires.
  - `IF-CHEM-REG-v1_ICP_REGISTRY_NOT_BUILT` is gone: the registry loads, or the model is MODEL_ERROR.
- **EM-N2** is the registry scenario `EM-N2-NOMINAL`. The model checks that it names exactly the tables of the parent's
  pinned `n2_n.toml` (addendum 02: IDENTICAL). Reaction ids are now registry channel ids.
- **Status propagation reads the registry:**
  - G-A930-AIR and the tier-1 gaps;
  - SP-04: SB-NO for every AIR composition, and SB-He / SB-Ar above the 1 % screen;
  - SP-05: NEG-CRIT is NOT_EVALUABLE, so DOM-12 applies;
  - OQ-NPICP-04: CA-ICP-v1 is NOT_RUN;
  - SP-07: XE is evaluated on its own registry.
- **Outputs.** At the solution, each reaction carries its direct rate, the `.dat` interpolation and their relative
  difference (UQ-06). OUT-14 provenance carries the registry labels and sha256.

## Admission rule (prereg §17)

| # | rule | state |
|---|---|---|
| 1 | prereg and lock committed | met |
| 2 | every LC, CC, NV, FC item passes under `cargo test --workspace --locked` | met for every exercisable item; LC-11 not exercisable (CM-PRED gate); **NV-06 partial**: 32 of 43 channels (below) |
| 3 | the abep-chem rate evaluator is admitted | **met on committed evidence**: C-ABEP_SIM_RATE_TABLES_PY `parity_report_v1` ADMITTED / PARITY_PASS, verified by abep-icp on every load. The ledger row still reads PYTHON_REFERENCE until lane A1 applies that report's request |
| 4 | verify items on admitted paths cleared | **open**: VER-01, VER-12 on every sustained case; VER-06, VER-02 (now also on the registered-rate path), VER-07, VER-08, VER-11 on their paths; CM-PRED VER-03..05, VER-13 |
| 5 | admission record (Rust commit, test log, lock sha256) | **open**: integration-line action |

VERIFIED is not claimed.

## NV-06: direct integral vs `.dat` interpolation (all 43 AIR channels)

The relative difference is (k_dat − k_direct) / k_direct, at T_e = 2, 3, 5, 7.5, 10, 15, 20 and 30 eV.

- **On table rows** (3/2 T_e an integer): |difference| ≤ 4.4e-7. The `.dat` holds the same integral printed to 7 digits.
- **Between rows,** linear interpolation on the 1 eV grid overestimates the steep threshold rates:

| channel group | T_e = 3 eV | T_e = 5 eV |
|---|---|---|
| N₂ → N²⁺ + N | +238 % | +31 % |
| N → N²⁺ (three HMS members) | +153 % | +18 % |
| N₂ → N₂²⁺ (uncertainty variant) | +108 % | +11 % |
| N⁺ → N²⁺ | +59 % | +7.1 % |
| N₂ → N⁺ + N (lower / upper) | +44 % / +42 % | +6.1 % / +5.7 % |
| N₂ → N₂⁺ | +16 % | +1.9 % |
| N₂ dissociation | +10 % | +1.1 % |
| 16 electronic channels | ≤ 4.7 % | ≤ 0.35 % |
| rotational and elastic | ≤ 0.26 % | ≤ 0.1 % |

- **Withheld** (INCOMPLETE_EVIDENCE, `EQ-06_REPRESENTATION_NOT_REGISTERED:<channel>`): `AIR-ION-04/ionization_N` and
  `AIR-EXC-02/excitation_N2_vib_0_to_{1..10}`.

This is the effect EQ-06 expects: direct evaluation was chosen because the 1 eV grid is too coarse for threshold rates
at low mean energy. UQ-06 would carry the difference as a scenario pair in the OUT-13 envelope, which stays
NOT_EVALUATED until abep-rng is admitted.

## Registered-rate solve (SYNTHETIC_TEST_ONLY)

The case exercises EQ-06 inside a solve:
- a floating tube with N₂ at 1 Pa and P_abs = 20 W, in CM-ABS;
- the registered channels `AIR-ION-03`, `AIR-EL-01` and `AIR-DIS-01`;
- species and process classes that are synthetic.

Result: CONVERGED, T_e = 4.982 eV, n_e = 5.71e16 m⁻³. The scan ends at 30 eV.

- Each reaction's rate equals the registry direct rate at the converged T_e, bit for bit.
- The particle balance n k_iz V = u_B Σ hA closes to 1.1e-16.
- T_e is identical at 20 W and 200 W.
- A second run is byte-identical.
- The `.dat` would have given +1.9 % (ionization) and +1.1 % (dissociation) at this T_e.

No number from this case is evidence. Every output is labelled SYNTHETIC_TEST_ONLY.

The eight v1 synthetic cases reproduce their v1 values exactly.

## Fail-closed chemistry tests (NP-ICP-CHEM-AIR FC-CHEM-01..10)

All ten are asserted under `cargo test` (`crates/abep-chem/tests/icp_registry.rs` and abep-icp `fail_closed.rs` /
`chemistry_registry.rs`):
- FC-CHEM-01: a missing or differing validity entry;
- FC-CHEM-02: a rate beyond its limit is refused;
- FC-CHEM-03: charge, nuclei or E_r below the formation energy;
- FC-CHEM-04: a changed pin;
- FC-CHEM-05: an O target bound to non-O data;
- FC-CHEM-06: AIR_PRIMARY today;
- FC-CHEM-07: He above and below the screen;
- FC-CHEM-08: NEG-CRIT not evaluable;
- FC-CHEM-09: mixed Xe / air;
- FC-CHEM-10: Hall files unchanged.

AD-AIR-10 also needs these tests, but AIR admission stays blocked by every other AD-AIR item.

## Evaluable today

| mode | state |
|---|---|
| AIR_PRIMARY, EM-O2B | INCOMPLETE_EVIDENCE: `NP_ICP_CHEM_AIR_NOT_ADMITTED`, plus the tier-1 gaps AIR-ION-02, -05, AIR-DIS-02, AIR-EXC-04, -05, -09, AIR-EL-03, -04, AIR-WALL-01..03 and AIR-NL-02, plus `SP-04…:SB-NO` and DOM-12 |
| XE_CONTINGENCY, EM-XE | INCOMPLETE_EVIDENCE: CHG-04, `NP_ICP_CHEM_AIR_XE_NOT_ADMITTED`, plus XE-ION-01, XE-EXC-01, XE-EL-01 and XE-WALL-01; no AIR item |
| EM-AR | INCOMPLETE_EVIDENCE: CHG-05 |
| EM-N2 | INCOMPLETE_EVIDENCE (below) |

EM-N2 in detail:
- 18 of the 29 nominal channels now have a direct rate.
- Withheld:
  - the 11 channels without a representation;
  - OQ-NPICP-04 (CA-ICP-v1 not run);
  - the process-class gate;
  - every v1 physical input: IN-08, IN-10, IN-11, IN-12, IN-17, DOM-06.
- No geometry or operating point was invented.

## Implementation choices (full list in the JSON, INT-16..INT-23)

- **INT-16, T_e scan with registered tables.** With registered tables, the scan ends at the highest T_e every table
  admits. For the 45 eV tables that is 30 eV, which is also the D-CHEM upper bound. That end is a scan node and is
  reported as `IN-24_T_E_SCAN_END`.
  - IX-05 forbids a rate beyond a verified limit.
  - Any root beyond the end would be OUT_OF_DOMAIN.
  - D-CHEM is scanned completely.
  - Synthetic sets keep the 0.1–150 eV grid.
  - For owner acknowledgement.
- **INT-17, CV-03 formation energies.** Neutrals are 0. An ion takes the least energy over its registered ionization
  routes, because the N²⁺ formation energy is route-dependent by 1.5e-4 eV (v1 OBS-01).
- **INT-18, `xs/` contents.** `xs/` also holds the reused tables' representations. The build plan names `xs/` for new
  tables only, but EQ-06 / IX-01 need a representation for every table used.
- **INT-19, synthetic verification sets.** SYNTHETIC_TEST_ONLY sets may reference registry channels, for
  verification only.
- **INT-20, admission source.** Item 3 reads the pinned admission record, not the ledger.
- **INT-21, electron mass.** The integral keeps the reference electron mass 9.10938e-31 kg, which the frozen tables were
  integrated with. The difference from CODATA is 2.0e-7 in k.
- **INT-22, feed composition.** For SP-04, a screened species present in a feed counts as above the screen.
- **INT-23, IN-05 status.** IN-05 stays INCOMPLETE_EVIDENCE as in v1; SP-06 is subsumed.

## Preregistration consistency

The NP-ICP-CHEM-AIR build plan and the NP-ICP-NEUTRALIZER preregistration with its addenda do not disagree on the
registry interface. Addendum 02 maps every chemistry item as IDENTICAL or STRICTER_OR_EQUAL. Two points were silent,
and both were handled without relaxing anything:
- where the reused tables' representations live (INT-18);
- where the consumer pins the registry. abep-icp pins `ICP_CHEM_PINNED.toml`, which pins every registry file.

## Still open

- Verification addenda for VER-01, VER-02, VER-06, VER-07, VER-08, VER-11 and VER-12 (CM-PRED also needs VER-03..05
  and VER-13).
- The prereg findings PF-01 and PF-02, and the gaps GAP-01..05: owner addenda or v2.
- The admission record (item 5).
- NV-06 for `ionization_N` and the vibrational channels. This needs a lawfully registered representation and, for the
  rate fits, an admitted evaluator.
- CA-ICP-v1 / OQ-NPICP-04.
- AIR_PRIMARY admission (AD-AIR-01..10, BP-S2..S9) and XE admission (AD-XE-01..06, BP-X1..X4).
- OQ-CHEM-05 / -06, used as drafted.
- INT-16 and INT-17.

Ledger request (lane A1 owns `migration_state_v1.json`): NP-ICP-NEUTRALIZER stays RUST_IMPL; its verification
evidence becomes `verification_report_v2.json` with Rust commit `e404c15`. Before that, the C-ABEP_SIM_RATE_TABLES_PY
row should apply its own report's request (PYTHON_REFERENCE → ADMITTED).
