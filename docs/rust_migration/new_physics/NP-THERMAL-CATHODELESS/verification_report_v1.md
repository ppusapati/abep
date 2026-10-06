# NP-THERMAL-CATHODELESS verification report v1

`verification_report_v1.json` is authoritative. This file restates it for people.

* **Model:** NP-THERMAL-CATHODELESS 1.0.0, the cathodeless Hall + downstream RF/ICP neutralizer lumped thermal network.
* **Preregistration:** `prereg_v1.json` sha256 `e3e6859c…`, `PREREG.md` `e3337c8f…`. Both match `prereg_lock_v1.json`.
* **Implementation:** crate `abep-subsystems`, module `thermal`, commit `fedc15a`. Built with rustc 1.94.1.
* **VS-NET:** `verification/vs_net_v1.json`, sha256 `64c4bf33…`. It was registered alone in `c3086e4`, before the
  implementation commit and before the scored run.
* **Scored run:** `cargo run --example np_thermal -- verify` at `fedc15a` on a clean tree. The run record is embedded in the JSON.

## Verdict

* **VERIFIED** under ADM-03. Every analytic case, every conservation criterion that can be evaluated inside the model,
  FT-01..FT-18, DET-01..DET-03, IV-01 and IV-02 meet their preregistered criteria.
* **CONS-L1** is evaluated, by its own text, in the SC-WP-05 system energy-ledger check, which does not exist yet. It is
  recorded `DEFERRED_TO_SYSTEM_LEDGER_CHECK` (see Q-02).
* **IV-03** is `NOT_PERFORMED`, because no licensed copy of the text is available here. ADM-03 requires it only when it
  is performed.
* **Validation status:** `NOT_VALIDATED`. Verification is not validation (ADM-05).
  * Anode and coupled H-1/ICP thermal closure stay UNRESOLVED.
  * No thermal result is ever reported as PASS.
* **Admission status:** NOT YET ADMITTED. The ADM-04 steps are listed below.

## Cases

Observed values are the worst over all sub-cases. They come from synthetic vectors (SYNTHETIC_TEST_DATA_NOT_EVIDENCE).

| id | criterion (prereg) | observed | status |
|---|---|---|---|
| AL-01 | radiator, 54 cases, \|ΔT\| ≤ 1e-6 K | 4.5e-13 K | met |
| AL-02 | series conduction, 54 cases, \|ΔT\| ≤ 1e-6 K; \|flow − Q\| ≤ 1e-9 Q + 1e-9 W | 5.7e-14 K; flow error 1.7e-4 of bound | met |
| AL-02b | Kirchhoff linear k(T), 24 cases, \|ΔT\| ≤ 1e-6 K | 0.0 K | met |
| AL-03 | first-order transient: (a) ≤ 1e-3 \|T∞ − T0\| at τ/1000; (b) \|p_obs − 1\| ≤ 0.1 at τ/100; (c) CONS-T1 | (a) 0.18 of bound; (b) 0.0030; (c) met | met |
| AL-04 | two-surface enclosure: (a) 1e-9 relative; (b) \|ΔT\| ≤ 1e-6 K, 225 cases | (a) 2.3e-6 of bound; (b) 4.5e-13 K | met |
| AL-05 | VS-NET zero load, T_s ∈ {3, 250, 300} K: \|T − T_s\| ≤ 1e-6 K; \|flow\| ≤ 1e-9 W | 0.0 K; 0.0 W | met |
| AL-06 | VS-NET step load to 30 τ_max: CONS-T1; \|T(t_end) − T_steady\| ≤ 1e-3 K | 2.8e-12 K; 6152 steps; cumulative 7.2e-7 J | met |
| AL-07 | coaxial disks (C-41) accepted; F perturbed 1e-6 and row sum perturbed 1e-6 refused | CONVERGED; MODEL_ERROR ×3 (reciprocity / summation) | met |
| AL-08 | 4-patch sphere: (a) \|q_k\| ≤ 1e-12 σ A T⁴; (b) Q_kl to 1e-9 relative | (a) 0.0; (b) 2.1e-7 of bound | met |
| AL-09 | environment plate, 64 cases: \|ΔT\| ≤ 1e-6 K; components to 1e-12 relative | 1.1e-13 K; 1.4e-16 | met |
| AL-10 | interface bookkeeping and refusals on VS-NET | 35 receivers exact (1.9e-16); IFH-2/3/4, IFI-2/3/4/5, missing key MODEL_ERROR; TBD → INCOMPLETE_EVIDENCE; NOT_EVALUATED → NOT_EVALUATED | met |
| AL-11 | winding R(T): 8 cases \|ΔT\| ≤ 1e-6 K; runaway OUT_OF_DOMAIN | 5.7e-14 K; OUT_OF_DOMAIN, no temperature | met |
| CONS-S1 / S2 | ≤ 1e-9 Q_scale + 1e-9 W | max 6.6e-4 of bound | met |
| CONS-T1 | energy integral per step and cumulative | max 2.8e-5 of bound | met |
| CONS-T2 | \|T_dt − T_dt/2\| ≤ 1e-2 K | max 0.99 of bound (step doubling holds it) | met |
| CONS-T3 | periodic ≤ 1e-3 K | 3.7e-4 K | met |
| CONS-I1 | IFH-3/4, IFI-3/4/5 with ε_if | hold on the consistent set; violations refused | met |
| CONS-I2 | deposition bookkeeping 1e-12 relative + 1e-12 W | 0.0 | met |
| CONS-L1 | system energy ledger < 2 % (SC-WP-05) | booked flows reported raw | deferred |
| FT-01 | flight Hall keys from the EMPTY credible set → NOT_EVALUATED, CREDIBLE_HALL_TRANSPORT_SET_EMPTY | NOT_EVALUATED, asserted explicitly | met |
| FT-02 | screening candidate → NOT_EVALUATED; unpinned commit → MODEL_ERROR | as expected | met |
| FT-03 | TBD / TBD_AFTER_EVIDENCE / OPEN → INCOMPLETE_EVIDENCE listing ids | as expected | met |
| FT-04 | missing evidence_class / uncertainty / applicability_domain / validation_status, wrong units → MODEL_ERROR | as expected | met |
| FT-05 | synthetic record in a non-synthetic case → MODEL_ERROR | as expected (also the reverse mix) | met |
| FT-06 | property outside range → OUT_OF_DOMAIN, no temperature | as expected (solution and T_init) | met |
| FT-07 | Bi > 0.1 (non-synthetic) → OUT_OF_DOMAIN naming the node | 12 nodes named; low-Bi companion CONVERGED | met |
| FT-08 | Newton / step / periodic caps → MODEL_ERROR | NEWTON_CAP / STEP_HALVING_CAP / PERIODIC_CAP | met |
| FT-09 | floating node → MODEL_ERROR | as expected | met |
| FT-10 | refused vocabulary (cathode family, C1) → MODEL_ERROR | 21 sub-cases | met |
| FT-11 | hall_c1_reference → MODEL_ERROR | as expected | met |
| FT-12 | active_cooling / icp_assist_magnet → OUT_OF_DOMAIN | as expected; flow_control_icp_feed accepted | met |
| FT-13 | identity violations → MODEL_ERROR | asserted in AL-10 | met |
| FT-14 | D-07 violations → MODEL_ERROR | asserted in AL-07 | met |
| FT-15 | design state outside design_states_v2 → OUT_OF_DOMAIN | as expected; a registered state CONVERGED | met |
| FT-16 | CAND-01 in flight → MODEL_ERROR; allowed and labelled in PARAMETRIC | as expected | met |
| FT-17 | output key scan; validation_status NOT_VALIDATED | 2583 keys, 3 outputs, clean | met |
| FT-18 | NOT_EVALUATED key → NOT_EVALUATED, never zero-filled | as expected; a value under NOT_EVALUATED is refused | met |
| DET-01 / 02 / 03 | byte-identical (2 runs; 4 threads); provenance fields | identical; complete | met |
| IV-01 | Python scratch: 1e-6 K steady, 1e-2 K transient, 1e-8 relative energy | closed forms ≤ 4.5e-13 K; VS-NET steady 6.8e-11 K (Gauss–Seidel); transient vs BDF2 2.3e-3 K; energy ≤ 3.2e-13 | met |
| IV-02 | Howell C-40 / C-41 three-surface hand solution, 1e-9 relative | 4.2e-15 | met |
| IV-03 | standard-text worked examples | not performed | — |

**Additional checks.** These go beyond ADM-03, and both are met:

* E-12 / CONS-T3: the orbit-periodic mean equals the orbit-average steady temperature (333.33 K).
* D-04 / D-05 bench domain.

**IV-01.** It is a cross-check, not a reference.

* It ran as a Python 3.11.15 / numpy 2.4.4 scratch script, sha256 `c5cc50dd…`.
* It is not committed, and it is not a CI dependency.

## Outputs that stay NOT_EVALUATED / INCOMPLETE_EVIDENCE today

| output | status | reason |
|---|---|---|
| map-derived Hall heat | NOT_EVALUATED | The credible transport set is EMPTY (NE-01; asserted in FT-01 and in the prereg-binding test). |
| Hall keys without a producer (anode, pole, plasma radiation, return-to-ICP, plume) | NOT_EVALUATED | NE-11 / CF-07. A key is never zero-filled (FT-18). |
| RF/ICP heat in flight | NOT_EVALUATED | NP-ICP-NEUTRALIZER is not admitted (NE-02). |
| spacecraft interface; every FLIGHT_CONDITIONAL run | NOT_EVALUATED | There is no host thermal ICD (NE-07 / NE-12). |
| flight view factors and attitude | NOT_EVALUATED / INCOMPLETE_EVIDENCE | NE-08 |
| geometry, emittances, conductances, partitions | INCOMPLETE_EVIDENCE | NE-03, NE-04, NE-05, NE-10 |
| anode / collector materials | INCOMPLETE_EVIDENCE | The materials are OPEN (NE-06). CAND-01 in a flight case is MODEL_ERROR. |
| measured validation | NOT_EVALUATED | NE-09. Every output is NOT_VALIDATED. |

## Implementation interpretations

The JSON lists IMPL-01..IMPL-15. The main ones:

* **IMPL-01.** The reduced analytic setups run in scope `ANALYTIC_REDUCED_NETWORK`, which is allowed only in
  SYNTHETIC_VERIFICATION. Every other case class enforces the registered node set and its REQUIRED nodes.
* **IMPL-02.** The value-record vocabulary has no TBD. A "TBD key" is the producer status INCOMPLETE_EVIDENCE.
* **IMPL-03.** The prereg registers no evaluation temperature for a temperature-dependent contact conductance. v1
  therefore accepts only a temperature-independent h_c and refuses any other form.
* **IMPL-04 / 05.** Step doubling accepts the full step and uses the half steps as the estimator. Newton iterates stay
  inside the property ranges. A direction blocked at a range end is OUT_OF_DOMAIN.

## Findings and open questions

* **F-01 / Q-01 (integration conflict).** The NP-ICP v1 prereg publishes the label `IF-ICP-THERMAL-v1` with eight extra
  keys and an N_MOUNT induced share. This consumer implements the thermal prereg (IK-01..IK-07) and refuses unknown keys
  with MODEL_ERROR. Integration needs IF-ICP-THERMAL-v2 on both sides (CC-02, OQ-NPT-02, CF-04).
* **F-02 / Q-02.** Does ADM-03 need CONS-L1, the system ledger check, before VERIFIED?
* **F-03.** D-07 allows a reciprocity error of 1e-9 relative. CONS-S2 sees internal exchange only through that defect.
  A view-factor set at the D-07 limit could therefore end MODEL_ERROR (fail-closed).
* **F-04.** VS-NET was redesigned before registration so that τ_max bounds its slowest mode (the AL-06 premise).
* **Q-03.** OQ-NPT-01..10 stay open.

## Missing for admission (ADM-04) and validation

* **ADM-04:**
  * the migration-ledger flip, owned by lane A1 (requested in the JSON);
  * a named CI step bound to the prereg sha256. The `rust-workspace` workflow already runs these tests through
    `cargo test`, including the lock binding.
* **Validation:**
  * EV-01 / EV-02 bench data (none yet);
  * EV-03 applicability (V-10, OQ-NPT-06);
  * EV-04 sources (V-11);
  * the P3-C-01..05 correlation plan and the owner residual band (VC-04).
