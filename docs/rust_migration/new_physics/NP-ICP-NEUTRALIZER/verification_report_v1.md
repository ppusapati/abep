# NP-ICP-NEUTRALIZER v1 — verification report v1

| item | value |
|---|---|
| model | `NP-ICP-NEUTRALIZER`, model_version `1` (NEW_PHYSICS; no Python reference; nothing from `plasma_chem.py`) |
| contract | `prereg_v1.json` `5d496ea6…` + `PREREG.md` `3af97940…` (lock `prereg_lock_v1.json` `e98747e0…`), `addendum_01_a9_30.json` `f8e12249…`; chemistry contract NP-ICP-CHEM-AIR v1 (lock `f42c2269…`) |
| implementation | `crates/abep-icp`, Rust commit `f4b615fb43172658485d4c78b0f83c2b67f318ac` (branch `lane-np-icp-impl`, base `a1baee1` fast-forwarded to integration head `7f2d6c5`) |
| toolchain | rustc / cargo 1.94.1 |
| tests | abep-icp 57, workspace 116; 0 ignored; `cargo fmt -- --check`, clippy `-D warnings` clean |
| **verification status** | **`IMPLEMENTED_UNVERIFIED`**. Software admission items 3, 4 and 5 are open (below). |
| **validation status** | **`NOT_VALIDATED`** on every output (no P1 / P2 record; published analogs blocked) |
| machine-readable | `verification_report_v1.json` (authoritative; measured values from `cargo run -p abep-icp --example verification_table --locked`) |

The lock hashes were recomputed before implementation and are verified on every `IcpModel::load`. The preregistration was
not edited. Every number in the suite comes from `SYNTHETIC_TEST_ONLY` inputs and verifies the implementation only.

## Admission rule (prereg §17)

| # | rule | state |
|---|---|---|
| 1 | prereg and lock committed | met |
| 2 | every LC, CC, NV, FC item passes under `cargo test --workspace --locked` | met for every exercisable item; LC-11 not exercisable (CM-PRED gate); NV-06 partial |
| 3 | the abep-chem rate evaluator is admitted | **open**: no abep-chem crate; `rate_tables.py` is still the Python reference |
| 4 | verify items on admitted paths cleared | **open**: VER-01 and VER-12 on every sustained case; VER-06 (saturated collector), VER-02 (elastic), VER-07, VER-08, VER-11 on their paths; CM-PRED needs VER-03..05, VER-13 |
| 5 | admission record (Rust commit, test log, lock sha256) | **open**: integration-line action |

Ledger request (lane A1 owns `migration_state_v1.json`): NP-ICP-NEUTRALIZER `NOT_STARTED` → `RUST_IMPL`. VERIFIED is not
claimed.

## Per-case verification table

| id | preregistered criterion (short) | measured | result |
|---|---|---|---|
| LC-01 | T_e power-independent, = independent root, ≤ 1e-9 | max rel 1.5e-16 | met |
| LC-02 | n_e/P_abs = 1/(e u_B Σ hA (E_iz + 2T_e + T_e/2 + V_s)), ≤ 1e-9 | max rel 4.7e-16 | met |
| LC-03 | P_abs = 0: CONVERGED / NOT_SUSTAINED, exact zeros; trivial-branch RF chain closes | exact zeros; (P_abs, Q_coil) = (0, P_del) | met (CM-PRED part is the gate) |
| LC-04 | η_p = 1/(1 + R_ant/R_p) to 1e-12; at 0: η_p = 1, Q_coil = 0 exactly | exact | met |
| LC-05 | I_e,cap ≤ thermal limit (1 + 1e-12); equality ≤ 1e-9 when saturated | rel 1.7e-16; max ratio 1 + 2e-16 | met (saturation branch: VER-06) |
| LC-06 | I_e,cap ≤ ion-collection and production limits; all floating → 0 exactly | max ratios 0.171, 0.0149; 0.0 | met |
| LC-07 | V_s = (T_e/2) ln(M/2π m_e) to 1e-12; V_s/T_e → 4.7 (Ar) | rel 0; 4.680 | met |
| LC-08 | u_B ≈ 2.9e3 m/s; h_R = 0.8/3, h_L = 0.86/√8; both ≈ 0.3; h_R → 0.4 | 2906 m/s; 0.2667; 0.3041 | met |
| LC-09 | n = Γ_in/(¼ v̄ A) to 1e-12; v̄(N2, 293 K) ≈ 470; C′ ≈ 117.5 (2e-3) | rel 0; 470.58; 117.65 | met |
| LC-10 | partition and bias closures ≤ 1e-10; Q_j = L_j + C_j ≤ 1e-12 vs independent kinetic energy; floating C_j = 0 | ≤ 6e-16 | met |
| LC-11 | R_p → 0 as n_e → 0 (EQ-14, after VER-03) | — | not exercisable: CM-PRED is a gate; NOT_EVALUATED asserted |
| CC-01 | particle balance per species ≤ 1e-10 | ≤ 3.6e-16 | met (neutral rows in FLOW_BALANCE only) |
| CC-02 | element conservation ≤ 1e-10 | ≤ 2.7e-16 | met (FLOW_BALANCE) |
| CC-03 | Σ I_j = 0, floating I_j = 0, production = loss | ≤ 7.9e-16 | met (normalisation GAP-05) |
| CC-04 | RF chain ≤ 1e-10 of P_fwd | 1.4e-16 | met (CM-CAL, synthetic P2 point) |
| CC-05 | RF-powered, bias, combined closures, every bounding assignment; deposited keys ≥ 0 | ≤ 2.5e-15 | met |
| CC-06 | bus sum, losses ≥ 0, P_RF,DC ≥ P_fwd; violating η_RF refused | 0.0; refusal asserted | met |
| CC-07 | formation energy created = released + carried out | ≤ 3.4e-16 | met (not exact for the N2/N set: OBS-01) |
| NV-01..05 | byte identity; thread independence; residuals reported; every root reported; non-finite → MODEL_ERROR | — | met |
| NV-06 | direct integral vs `.dat` per reaction | `.dat` side for all 29 N2/N reactions | partial: direct side NOT_EVALUATED (abep-chem) |
| FC-01..FC-16 | fail-closed assertions of the prereg | — | met (each asserted, nothing skipped) |
| G-A930-AIR | AIR_PRIMARY INCOMPLETE_EVIDENCE `NP_ICP_CHEM_AIR_NOT_ADMITTED` + tier-1 gaps; no N2 surrogate for air; XE isolated | — | met |
| A9.30 bus | IF-ICP-BUS-v1 targets `bus_power_boundary_a9_v2` only | — | met |

Synthetic case suite (all CONVERGED; T_e ≈ 2.6–3.0 eV, n_e ≈ 3.4–6.6e17 m⁻³, φ_p ≈ 9.4–14.4 V): floating tube,
CFG-CAP-OFF saturated and retarding collector, excitation bounding pair, X⁺ → X²⁺ (n_e does not cancel), FLOW_BALANCE,
CM-CAL with bus, P_abs = 0. Largest conservation / closure residual over the suite: 2.5e-15.

## Evaluable today

| configuration / mode | state |
|---|---|
| CFG-CAP-OFF + CM-ABS | implemented and verified on synthetic inputs; no real-gas case has its inputs registered |
| CM-CAL | implemented at a registered, validated, H_MODE P2 point; no P2 data → NOT_EVALUATED (FC-04) |
| CM-PRED | status gate only (VER-03..05, VER-13; antenna IN-09 TBD); never admissible |
| CFG-FLIGHT-HALL-ON | NOT_EVALUATED contract (IN-21; credible Hall set EMPTY) |
| AIR_PRIMARY, EM-O2B | INCOMPLETE_EVIDENCE: `NP_ICP_CHEM_AIR_NOT_ADMITTED` + AIR-ION-02, -05, AIR-DIS-02, AIR-EXC-04, -05, -09, AIR-EL-03, -04, AIR-WALL-01..03, AIR-NL-02; DOM-12 |
| XE_CONTINGENCY, EM-XE | INCOMPLETE_EVIDENCE: CHG-04, `NP_ICP_CHEM_AIR_XE_NOT_ADMITTED`, XE-ION-01, XE-EXC-01, XE-EL-01, XE-WALL-01 |
| EM-AR | INCOMPLETE_EVIDENCE: CHG-05 |
| EM-N2 | INCOMPLETE_EVIDENCE (below) |

## N2 CFG-CAP-OFF CM-ABS demonstration: NOT_EVALUATED

Registered today: EM-N2, G-REUSE, CFG-CAP-OFF, 13.56 MHz, `n2_n.toml` (abep-n2n-0.11, every table sha256-verified).
No geometry or operating point was invented (CLAUDE.md rule 6). Missing, each reported by the model:

- `IN-08` absorbed power: flight setpoints TBD; no bench record with measured P_abs (VI-RF-05).
- `IN-10` geometry and effective volume: F6-X-01..05, 10..17 TBD (OQ-NPICP-12).
- `IN-11` electrode registration: P1-IT-36, ICD ICP-21; bias range for I_e,sat.
- `IN-12` neutral source: p_ICP (VI-GAS-03) or f_in / conductance (VI-GAS-04).
- `IN-17` ion-neutral cross sections or sourced h (CHG-06).
- `DOM-06` B_ICP,max (VI-HD-06; OQ-NPICP-03).
- `EQ-06` admitted abep-chem integrator; `IF-CHEM-REG-v1` ICP registry (NP-ICP-CHEM-AIR BP-S1).
- `OQ-NPICP-04` ICP-domain completeness audit; process-class gate (50 unaddressed species/class pairs).

Even with those inputs, the wall / outflow partition keys would stay withheld for N2 by GAP-01 and GAP-02.

## Findings for the owner (not resolved here; the prereg was not edited)

- **PF-01 (EQ-02).** The atom wall-recombination term removes (γ/2)·¼ n v̄ A_wall. NP-ICP-CHEM-AIR defines γ as the
  per-collision probability, for which the atom loss is γ·¼ n v̄ A. The [0, 1] envelope cannot reach the physical
  maximum. γ > 0 in FLOW_BALANCE is withheld (INCOMPLETE_EVIDENCE).
- **PF-02 (EQ-02).** Background inflow uses Σ A_open without τ while effusion uses A_open τ. For τ < 1 the no-plasma
  equilibrium is n_b/τ, not n_b. Withheld when n_b > 0 and τ ≠ 1.
- **GAP-01 (EQ-16 notes).** "In proportion to their loss channels" gives no operational wall / outflow split for neutral
  (elastic, vibrational, rotational) energy. The partition keys are withheld whenever such a channel exists, which is
  every real gas. The solve, I_e,cap and the bias keys are unaffected.
- **GAP-02 (EQ-16 / EQ-18).** Atom formation and fragment energy need atom loss channels (none in REGISTERED_PRESSURE).
  The partition is withheld when dissociation or dissociative ionization is present.
- **GAP-03.** CARRIED_OUT has no split between the open ends (withheld; not reachable today).
- **GAP-04.** Per-species σ_i gives per-species h, but EQ-08/09 define one h per surface. Multi-ion H-LIEB with
  distinct σ is withheld.
- **GAP-05 (CC-03).** "Relative to max |I_j|" degenerates when every surface floats. This implementation normalises
  by the largest current component instead.
- **OBS-01.** In the N2/N headers the N²⁺ formation energy is route-dependent (44.1354 vs 14.534 + 29.60125 eV, a
  difference of 1.5e-4 eV), so CC-07 is not exact for that set as registered.

## Implementation choices inside the prereg (full list in the JSON)

- Root-scan grid registered here (IN-24): T_e 0.1–150 eV with 301 log points; n_e 1e8–1e21 m⁻³ at 10 points per
  decade. Bisection runs to adjacent doubles (limit 400). φ_p is solved in closed form per collection regime. The T_e
  scan is wider than every chemistry domain, so a root outside the domain is reported OUT_OF_DOMAIN rather than missed.
- With several equilibria, all are listed and the point outputs are NOT_EVALUATED (no silent choice). FLOW_BALANCE
  follows its T_e branches across n_e; a sign change at a branch fold is MODEL_ERROR.
- CM-ABS with P_abs > 0 and no sustained state is MODEL_ERROR (CC-05: the power has no sink). CONVERGED NOT_SUSTAINED
  is reached only at P_abs = 0.
- Registration failures decide the status before input-domain verdicts, and every reason is listed.
- Z > 1 presheath energy Σ Z Γ T_e/2 and I_production = e V Σ ΔZ R are identical to the registered forms for Z = 1
  (the Z > 1 forms sit on the VER-08 path).
- Formation energy of ions neutralized at the electron sink is booked in Q_icp_extraction_W (EQ-18).
- The FC-04 status follows the prereg (NOT_EVALUATED), not the lane brief (INCOMPLETE_EVIDENCE). Direct Maxwellian
  rates come only from the admitted abep-chem integrator (EQ-06, IF-CHEM-REG-v1).
