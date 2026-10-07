# NP-ICP-NEUTRALIZER model_version 2 — verification report v1

Human-readable companion of `verification_report_model_v2_v1.json`, added on 2026-10-07 after that report. The JSON governs and is unchanged. Report v2 (`verification_report_model_v2_v2.json` / `.md`) supersedes its status statement and corrects one omission (VER-02). It does not edit this report.

| item | value |
|---|---|
| model | `NP-ICP-NEUTRALIZER`, model_version `2`, added beside v1 in `crates/abep-icp/src/v2` |
| contract | prereg v2, lock `a180ceef…`; the v1 lock is verified on load as predecessor |
| implementation | commit `edbbfe1` (v1 path additive only; v1 results byte-identical to base `1c9e87f`) |
| verification status | **IMPLEMENTED_UNVERIFIED** |
| validation status | **NOT_VALIDATED** on every output |

## Admission rule (prereg v2 `admission_rule_v2`)

1. Record and lock committed: **met** (`7a26d39`).
2. LC / CC / NV / FC items under `cargo test --workspace --locked`: **met** for every item with a code path. The workspace gave 455 passed, 0 failed, 2 ignored (the registered platform tests PT-01 / PT-02).
3. abep-chem evaluator admitted: unchanged.
4. Verify items on admitted paths cleared: **not met**. The report listed VER-01, VER-06, VER-07, VER-08, VER-11, VER-12 and VER-20..VER-25 as open.
5. Matched consumers: **met in code**:
   - NP-THERMAL 2.0.0 consumes IF-ICP-THERMAL-v2 with the identical key table (`33e495ad…`);
   - the IF-ICP-BUS-v2 consumer passes LC-18.
6. Admission record: not written.

## Verification cases

- **LC-12:** PF-02 background equilibrium. n = n_b for T_b = T_g, and n = n_b v̄_b / v̄ otherwise (flag NON_ISOTHERMAL_PASSAGE), to 1e-12 for τ ∈ {1, 0.5, 0.1}.
- **LC-13:** PF-01 recombination in a closed vessel. Atom density and the S/2 molecule source match to 1e-12 from the solver's own balance rows. At γ = 1 the loss is ¼ n v̄ A. Every {0, 1} γ vertex member solves with CC-01..CC-03 ≤ 1e-10.
- **LC-14:**
  - One ion species: the H-LIEB member is bit-identical to v1.
  - Two species: the h bounds, the n_e,j relation and the floating-sheath flux hold to 1e-12.
  - The three members H-MS / H-LO / H-HI each pass CC-01 / CC-03.
- **LC-15:** every ED-08 disposition vertex places the full class energy on its destination to 1e-12. The OUT split is A_j τ_j with τ registered, and the OUT[UP] / OUT[DOWN] pair without.
- **LC-16:** CC-03 v2 ≤ 1e-10; NOT_SUSTAINED gives exact zeros.
- **LC-17:**
  - RF-S, RF, PL, B, S and CONS-I3 ≤ 1e-10;
  - SG-01 ≤ 1e-12 against the independent closed form;
  - Σ C_j = −Σ I_j V_j;
  - C_j = 0 exactly when all surfaces float.
- **LC-19:** the EQ-19 closed forms hold to 1e-12. λ_D uses the implementation's ε0 (VER-25 stays on the path), and s_j is NOT_EVALUATED (VER-22).
- **LC-20:** with the pinned N headers, E_form,ref(N²⁺) = 44.13525 eV. The direct route's excess is 1.5e-4 eV, and CC-07 ≤ 1e-10.
- **Fail-closed:** FC-14 and FC-16..FC-30, today's real-mode cases, the lock tamper check and NV-01 determinism.

## Implementation interpretations

- **GAP-04:** λ_i,s uses one cross section per ion species (the IN-17 registration form).
- **One ion species:** a single H-LIEB member is emitted; H-MS / H-LO / H-HI coincide by definition.
- **Partition-only gates** (D0, net atom consumption) are named on the IF-ICP-THERMAL-v2 record, not on the solve.
- **Member status:** a thermal member is CONVERGED only when every key is.
- **BUS2-07:** with no IN-19 registration, the variant slots are NOT_INSTALLED at exactly 0.
- **DOM-17:** a registered flight exposure model has no registered inflow form, so it is NOT_EVALUATED.
- **UQ-03:** sampling is NOT_EVALUATED until the admitted ABEP RNG exists.

No conflict with prereg v2 was found, and no frozen record was edited.
