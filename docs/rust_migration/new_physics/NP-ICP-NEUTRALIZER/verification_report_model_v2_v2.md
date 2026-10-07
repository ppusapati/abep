# NP-ICP-NEUTRALIZER model_version 2 — verification report v2

Human-readable companion of `verification_report_model_v2_v2.json`; the JSON governs. Report v1 (`verification_report_model_v2_v1.json` / `.md`) stays immutable, and every result of it that is not listed here still stands.

| item | value |
|---|---|
| verification status | **IMPLEMENTED_UNVERIFIED** (admission-rule item 4 not met) |
| validation status | **NOT_VALIDATED** |
| new commits | `6a4f961` (smoke case registration), `7d4bddb` (VER-23 consequence, adapter, smoke case) |
| tests | workspace 507 passed, 0 failed, 2 ignored (PT-01 / PT-02); test-register 0 violations; fmt and clippy clean |

**Correction to v1:** VER-02 was missing from the open list. The shared registration step puts it on the path of every set with an elastic momentum-transfer channel.

## Verify items

The verify gate (inherited from v1) clears an item only through an addendum that records a lawful source read. A derivation, a conservation check or a test does not replace the source text.

| item | on the v2 path | status | why open / what closes it |
|---|---|---|---|
| VER-01 | every sustained solve (EQ-03 cross-reference; LC-01 passes) | open | Lieberman & Lichtenberg 2005 is not in the repository, and no lawful copy is available here. Closed by an addendum with a lawful read of ch. 10. |
| VER-02 | sets with an elastic channel (EQ-07) | open | The elastic-loss form is cited from memory, and conservation cannot confirm a coefficient. Closed by an addendum confirming the form (a v2 prereg if it differs). |
| VER-06 | electron-saturation branch (EQ-09, I_e_sat sweeps) | open | Baalrud et al. 2007 is not in the repository (subscription journal; publisher hosts are blocked here). Closed by an addendum with a lawful read. |
| VER-07 | H-LIEB / H-MS with an open end | open | Chabert et al. 2012 is not in the repository. Closed by an addendum. |
| VER-08 | Z > 1 ions (EQ-04) | open | No registered source; a derivation does not satisfy the gate. Closed by an addendum with a lawful read. |
| VER-11 | only for a registered IN-23 disposition (none today) | open, not on a path | Closed by a disposition per state with its source, plus an addendum. |
| VER-12 | every sustained solve (surface energy terms) | open | Not sourced in the repository. Closed by an addendum with a surface-physics source. |
| VER-20 | PF-02 non-isothermal passage | open | LC-12 verifies the implemented form, not its premise. Closed by an addendum confirming τ reciprocity. |
| VER-21 | member H-MS | open | Baalrud, Hegna and Callen 2009 is not in the repository, and its preprint host is blocked here. Closed by an addendum. |
| VER-22 | none computed (s_j NOT_EVALUATED) | open, not on a computed path | Closed by an addendum confirming the Child-law form; s_j is then implemented under it. |
| **VER-23** | CPL-HON-05 (gated) | **cleared** | `verification_addendum_ver23_v1.json`, a read of the pinned HallThruster.jl `bfb3019f` (five files, sha256, line references). The coupling potential is the right-boundary input `cathode_coupling_voltage` [V], entering ΔV = V_L − V_R of the discharge-current integral, and Te_R = `cathode_Tev`. HALL_COUPLING_POTENTIAL_INPUT_UNVERIFIED is removed; CPL-HALL-ON-v1 stays NOT_EVALUATED. |
| VER-24 | CPL-HON-04 (gated) | open | No published extraction-boundary law has been located. Closed by a located, lawfully read source. |
| VER-25 | every sustained solve (λ_D) | open | CODATA 2022 ε0 is not registered in the repository; physics.nist.gov and arxiv.org are blocked by this session's network policy. The shared v1 constant cannot change. Closed by a lawful NIST read, recorded in an addendum (allow physics.nist.gov in the environment's network access, or register the value with its locator and sha256), then a v2-only constant. |

Not on any v2 path today: VER-03..05 and VER-13 (CM-PRED), VER-09 / VER-10 (no such registration in use), VER-19 (documentation only).

## Coupling smoke case (brief item 5)

One registered SYNTHETIC case: `coupling_smoke_v2_registration_v1.json`, case sha256 `a08a263c`, committed alone before its run. Its test is `crates/abep-mission/tests/coupling_smoke_v2.rs`. abep-mission already depends on both crates, so abep-subsystems gains no dependency (INV-A05 unchanged). The chain is NP-ICP v2 (CM-CAL) → IF-ICP-THERMAL-v2 adapter → NP-THERMAL 2.0.0 → IF-ICP-BUS-v2 → CONS-L1 v2.

- **Producer closures:** every closure CONVERGED, ≤ 1e-10.
- **Exactly once per key:** for every key TK-01..TK-13, deposited + exported + booked equals the key exactly (residual 0 against the CONS-I2 bound).
- **No loss, no double count:** the destinations sum to the slot-load sum, 36.01242 W, within 1.4e-14 W. The thermal CONS-I3 check is met (bound 3.6e-5 W).
- **Bus load planes:** BK-01..BK-03 equal the thermal record's TK-R2, TK-05 and TK-R5 exactly.
- **CONS-L1 v2 ICP account:** the ledger value equals the accounted value (36.01242 W, mismatch 0.0 W). The ledger P_loss of 5.84 W is supply loss outside the account. Relative residual 1.4e-16.
- **Fail-closed, adapter:** refuses a duplicated JSON key, the same watt under a second name, a dropped key, an unmapped status, a CONVERGED key without a value, a withheld key with a value, a key-row mismatch, a duplicated member, a v1 interface and another producer lock.
- **Fail-closed, downstream:** refuses a double-booked share (IFI2-08), a doubled key (IFI2-04) and an ICP slot claimed by two accounts (CONS-L1_DOUBLE_COUNT).

No conflict with prereg v2 was found, and no frozen record was edited. D0(N2) and the real-configuration f_up / TK-06 partitions stay open; no source for them is registered.
