# S2 (PRODUCTION-MODEL CHANGE) OWNER DECISIONS (A9.9) — verbatim record, 2026-10-01

Recorded verbatim from the owner's message of 2026-10-01 (session chat), answering group S2 (S2.1–S2.5) of
`docs/budgets/owner_decisions/OWNER_QUESTIONS_SEQUENCED_v1.md`. Machine-readable companion:
`OD_2026_10_01_A9_9_s2_model_change_owner_decisions.json`. Immutable after commit; later amendments are new addenda.

---

1. S2.1 — F1Q-01 — AUTHORISE THE PRODUCTION FIX.
Correct `IntakeSurface` in the production model. Do not retain the erroneous mass-fraction recombination and compensate only in the design-synthesis layer.
The species-resolved quantities shall be recombined according to their physical definitions:
   * drag/C_D using a species-consistent momentum/mixture dynamic-pressure formulation;
   * passive compression using the appropriate number/mole-based species treatment;
   * collected species flow using the species-resolved collection efficiencies rather than collapsing them prematurely to one mass-weighted efficiency.
The present approximately ×1.08 C_D and ×1.065 passive-compression bias identified by F1-01 is therefore treated as a model-consistency defect, not as an alternative modelling convention.
Requirements for implementation:
   * make the controlled production-code change;
   * add regression tests for pure species and mixtures;
   * preserve the pre-fix result as historical evidence;
   * update `docs/HISTORY.md`;
   * regenerate every affected golden and downstream F-lane artifact;
   * do not manually retune another coefficient to recover the previous results.
Decision: YES — controlled production fix authorised.
2. S2.2 — F1Q-04 — YES, BUILD FROZEN INTAKE SURFACE V2 AFTER S2.1.
Authorise a new versioned frozen intake response surface v2 covering the required atmospheric/envelope states instead of using bounded direct TPMC as a substitute away from the original build state.
Sequence is mandatory: implement S2.1 first, then rebuild the surface once.
The v2 build shall:
   * remain species-resolved;
   * cover the intended altitude/atmosphere/incidence/surface-state envelope used by the production model;
   * retain Maxwell and CLL cases as separate admitted physical scenarios where applicable;
   * use deterministic seeds and the registered convergence criterion;
   * retain unresolved-particle/convergence information;
   * contain full provenance, configuration and hashes;
   * be cross-checked against direct TPMC at selected build and held-out states;
   * fail closed outside its frozen domain — no silent extrapolation;
   * retain v1 unchanged for reproducibility of historical results.
Only after verification shall production references move from v1 to v2.
Decision: YES — authorised, conditional on S2.1 being implemented first.
3. S2.3 — OQ-F3-01 — REMOVE THE GENERIC ROTOR ALLOWABLE/FOS FROM QUALIFICATION; USE A REGISTERED MATERIAL-BASIS RECORD.
Do not make the existing uncited `safety_factor = 2.0` a permanent physical constant, and do not treat the current 827 MPa Ti-6Al-4V annealed-plate room-temperature value as universally applicable to the compressor rotor.
Modify the production model so rotor structural acceptance requires a registered rotor-strength basis containing, at minimum:
   * alloy/material specification;
   * actual product form;
   * heat treatment/condition;
   * applicable thickness/section;
   * rotor operating/design temperature;
   * cited statistical allowable basis;
   * yield allowable versus temperature;
   * ultimate allowable versus temperature;
   * density from the same controlled material definition;
   * applicable design/test factors;
   * maximum operating/design speed;
   * proof-spin/qualification basis where applicable.
The production code shall calculate margins against both yield and ultimate criteria rather than relying on one generic DB yield value.
Until those inputs are registered, a rotor may be explored as `PARAMETRIC_SENSITIVITY`, but it shall not return a qualified `rotor_ok = true`. The qualification result shall be `NOT_EVALUATED_MATERIAL_BASIS`.
The existing factor 2.0 may be retained only as an explicitly labelled legacy/conservative sensitivity case for comparison. It shall not be represented as a cited aerospace requirement and shall not silently control production sizing.
For the present Ti-6Al-4V candidate, obtain the allowable corresponding to the actual rotor stock/product form and worst relevant rotor temperature. Do not transfer the 827 MPa annealed-plate value to another product form merely because the alloy name is the same.
Once the rotor manufacturing route is selected, register the applicable structural factors and proof-spin requirement before design freeze.
Decision: replace the hard-coded structural assumption with a cited, product-form- and temperature-specific registered strength basis; fail closed until that basis exists.
4. S2.4 — UPSTREAM_ICD-Q7 — YES, ADD G-03 TO G-05 NOW.
Add the three convergence/domain outputs to the production gas-path modules now:
   * G-03 — compressor recirculation convergence: `DragCompressor.run()` must explicitly report convergence, iteration count and final residual. Reaching the iteration limit is not convergence.
   * G-04 — reservoir/chamber steady-state convergence: `Reservoir.steady_state()` must explicitly report convergence, iteration count and final balance residual.
   * G-05 — orifice sizing convergence/domain: `size_orifice_for_pressure()` must report the final pressure residual and whether the requested solution is bracketed/reachable. Returning a bracket endpoint is not evidence of convergence.
Preserve the raw numerical state for diagnostics, but any record whose required solver has not converged shall be flagged `MODEL_NOT_CONVERGED`/equivalent and shall not be admitted as valid evidence or silently propagated as a successful solution.
Adding the flags should not intentionally alter already-converged numerical solutions. Any unexpected numerical change requires investigation rather than golden updating by default.
Add regression tests and a `docs/HISTORY.md` entry.
Decision: YES — implement now.
5. S2.5 — F9-OQ-04 — AUTHORISE ALL FIVE CONTROLLED FIXES.
MCC-02 — Gaede clipping:
Fix. Preserve/report the unclipped Gaede characteristic. If the physical relation produces `K < 1`, do not silently convert that state into a valid `K = 1` compressor result. Flag it as outside the admitted model/stage-capacity domain and exclude it from valid design evidence. A clipped value may be retained only as a labelled diagnostic quantity.
MCC-03 — rotor allowable fallback:
Fix together with S2.3. Remove the uncited generic material-DB yield as an implicit production acceptance criterion. Rotor qualification must use the registered strength-basis record. Missing structural evidence gives `NOT_EVALUATED`, not an assumed PASS.
MCC-05 — `max_hits < 1` non-termination:
Fix. Validate the input before particle tracing. `max_hits` and related hit-budget parameters shall have valid positive integer domains. Invalid input shall be rejected explicitly; the routine must never hang or depend on accidental loop behaviour.
MCC-06 — unknown scattering-model fallback:
Fix. An unrecognised wall-scattering model shall raise/refuse an invalid configuration. It shall never silently fall back to Maxwell. Maxwell and CLL must be explicitly selected and recorded.
MCC-07 — invalid CLL accommodation coefficients:
Fix. Require finite CLL accommodation inputs inside their admitted physical interval [0,1] before simulation. NaN, infinity or out-of-range coefficients shall be rejected explicitly before entering the kernel; they shall not produce NaNs downstream or be silently clipped.
For all five changes:
   * add focused unit/regression tests;
   * run the complete golden suite;
   * document each change separately in `docs/HISTORY.md`;
   * regenerate downstream artifacts where results genuinely change;
   * preserve old benchmark/provenance records;
   * never retune unrelated parameters merely to reproduce the previous golden values.
Decision: YES — all five controlled model fixes are authorised.
