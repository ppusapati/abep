# GOLDEN DESIGN POINT / DEDICATED BASELINE RERUN OWNER DECISIONS (A9.18) — verbatim record, 2026-10-01

Recorded verbatim from the owner's message of 2026-10-01 (session chat). Machine-readable companion:
`OD_2026_10_01_A9_18_golden_and_baseline_owner_decisions.json`. Immutable after commit; later amendments are new addenda.

---

For both points, I would set the following decisions.

1. Golden design point — choose a new admissible, converged golden point. Do not keep a non-converged design as the canonical golden design point. That would conflict with the fail-closed convergence policy we have already adopted.

Keep the existing non-converged case unchanged as a historical/regression fixture, explicitly labelled something like `NONCONVERGED_REFERENCE` or `EXPECTED_NONCONVERGENCE`. It remains useful for proving that the solver correctly refuses invalid evidence. Then select a new admissible golden design point only from a point that:

* is inside the registered model domain;
* converges under the new G-03/G-04/G-05 rules;
* satisfies all applicable input-validation rules;
* has no silent clipping/fallback;
* is reproducible from frozen inputs;
* carries provenance and hashes.

Do not tune the new point merely to reproduce the old golden numbers. The new golden is allowed to move because the controlled S2 model changes legitimately change the admissible numerical baseline.
Decision: `NEW_ADMISSIBLE_CONVERGED_GOLDEN; RETAIN_OLD_AS_NONCONVERGED_REGRESSION_REFERENCE`.

2. Dedicated performance baseline — yes, rerun only after step 3 is merged. Nothing needs to be run on your machine now.

Once you tell me step 3 is merged, rerun the same dedicated-baseline procedure on the otherwise idle machine. That post-model-change run becomes the relevant performance baseline for any Rust admission decision. The earlier dedicated measurement remains valid historical evidence for the earlier code state, but it must not be used to admit Rust kernels against code that has since changed.
Keep the workload definition and the S10.1 thresholds unchanged so the before/after result is comparable; record the new commit SHA, workload hashes, machine/toolchain metadata, and timing results.
Decision: `RERUN_DEDICATED_BASELINE_AFTER_STEP3_MERGE_BEFORE_RUST_ADMISSION`.
So the immediate instruction to the development team is: replace the canonical golden with a genuinely converged admissible point, preserve the old non-converged case as an explicit failure-regression fixture, and do nothing about the performance rerun until you tell me step 3 has landed.
