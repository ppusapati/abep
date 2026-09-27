# Held-out Hall-transport validation pre-registration on H-1 (W5 DRAFT)

**Status: DRAFT_PENDING_OWNER. Not locked. No simulation run. No measurement exists.** This is follow-on
`fo_hall_validation_prereg_draft` (trigger `T_PIVOT_HALL_VALIDATION_PREREG_DRAFT`, owner disposition `od_hardware_pivot`,
workstream W5), at base commit `510e464`. The authoritative content is `hall_transport_v2_prereg_DRAFT.json`. This page
explains that file. `pin_inputs.py --check` verifies the sha256 pins, and `tests/test_hall_validation_prereg_draft.py`
checks the draft's invariants. Thresholds that are not in the RFP are **PROPOSED**. Tolerance values are
**TBD_FROM_INSTRUMENTATION** until the W4 audit exists.

**Name.** "v2" means this is the project's *second* Hall-transport validation pre-registration, after P5-N₂ v1. It is
**not** the "P5-N₂ v2" of Question A, which stays closed (A-NO). Nothing here is scored on P5-N₂ measurements, and the
chemistry domain does not change.

## 1. Purpose

The owner moved the decisive-thrust question to a common-hardware experiment. There is one Hall accelerator H-1 and one
cathode C-1, tested in three arms: HW-0 `hall_only`, HW-RF `rf_hall` and HW-ECR `ecr_hall`. Some of that experiment's
measurements should become **genuinely new predictive evidence** under the promotion rule
(`admission_record_schema_v1.json` `promotion_evidence_rule_2026_09_26`; `transport_ensemble_v0.json` `admission_rule`).
That rule needs evidence not used in selection, no retuning, and a ≤ 1/16.

This draft decides, before any data exist, which measurements are **registration inputs** and which are **held out**. It
also sets how the nine screening candidates are run, how out-of-domain runs are treated, the acceptance-criterion forms,
data custody and blinding, and the verdict logic.

## 2. Milestones

| milestone | role | what the next step needs |
|---|---|---|
| **A** conditional selection | Not required. LOCK-1 adopting package decision D-14-B costs no readings. Whether the hardware schedule waits for the blind prediction set PF-1 is owner decision VP-17 (§10): under the PROPOSED option it does not; under the alternative HOLD_S1B, S1b waits for a Julia campaign of roughly v1 size, which would be a schedule cost to Milestone A work. Under RELEASE_GATED, the publication embargo (§10) means a Milestone A disclosure of HW-0 values (R_arch, the knee) before PF-1 is frozen either waits or costs those conditions (automatic OUTPUTS_SEEN). | nothing from this lane |
| **B** physics-backed selection | **Primary.** In this set of workstreams, this is the only route by which a closure can be *admitted*. | owner decisions VP-01…VP-20; W4 audited uncertainties; W3 H-1 geometry release; S1a B(z); this draft's runnability gates RG-01…RG-12 (§11; only RG-01, RG-03, RG-04 and RG-05 map to lane-35 items: P6 and open decisions 10, 7 and 3); LOCK-H1; a PROMOTABLE outcome; O4-equivalent dispositions; an admission record. For `rf_hall`/`ecr_hall` absolute performance, also the inflow model change at `HALL_INLET_Z0` and O/O₂ chemistry. |
| **C** PDR freeze | none directly | everything for B, plus wall-life-grade maps and integrated mass, power, thermal, life, startup, cathode and mission closure |

Operating-model questions:

- **(i) What it says for conditional selection now:** nothing. This lane ranks nothing.
- **(ii) What blocks physics-backed selection:**
  - the credible set is empty;
  - this draft is not locked;
  - H-1 geometry and B(z) don't exist yet;
  - the solver has no inflow at the anode (the inflow gap);
  - there is no O/O₂ chemistry.
- **(iii) What could overturn it:**
  - chemistry-domain exits. In v1, 66 % of run-readings were OUT_OF_DOMAIN.
  - failure of the channel-length-unit transfer of ScaledGaussianBohm to H-1.
  - facility effects above the admissibility bound.

## 3. Relation to P5-N₂ v1

- The v1 outcome, **INCONCLUSIVE**, is permanent. This draft does not change it.
- No P5-N₂ measurement, score, decision or reconstruction is new evidence here. This follows Question A binding rule 2.
  The following are forbidden as targets, tolerance sources or registration inputs:
  - `hallthruster_bridge/validation/**`
  - the `measured` blocks of `cases/p5_n2.json`
  - `identification/**`
  - the P5 `bfield/**` files
- Only the v1 *rule text* is reused, as procedure and not as evidence:
  - the run statuses and the extinction addendum;
  - the O1 extinction definition, the O2 precedence and the O3 aggregation;
  - the structure of the O4 staged sensitivities.
- The P5-Xe evidence that selected the candidates stays the selection record. It is not counted twice.
- The P5 layer-1 calibration nuisance (registration, coil shape, divergence reading, ingestion interpretation) describes
  what *P5* was. It does not carry over to H-1, and it is never a design variable or grid axis.

## 4. Registration inputs versus held-out observables

**Principle.** Registration inputs describe what the H-1 experiment *was*. They are measured and enter the solver through
a mechanical rule fixed at lock. They are never fitted to a held-out observable.

There is no selectable set of registration hypotheses. P5 had one only because its geometry and field were unpublished.
Instead, each input's measurement uncertainty is propagated **blind** into a model-side u_reg, before any held-out
output reaches the physics track (under VP-17 HOLD_S1B, before any Hall-on reading). Each input is perturbed by ± its
audited standard uncertainty (RG-07a, required before PF-1), one at a time, and u_reg is the root-sum-square of the
half-differences per observable.

**How profile inputs are perturbed (PROPOSED, VP-20; fixed at LOCK-H1 before any S1a input is released).** Scalar
inputs (ṁ, T_feed, V_d, and each geometry dimension L_ch, r_in, r_out, anode position) are perturbed separately. B(z)
gets two separate modes: a uniform amplitude scale by (1 ± u_B,rel), from the probe calibration, and a rigid axial shift
by ± u_z, from the probe position relative to the anode. There is no pointwise envelope and no shape deformation. f_div
enters C-T directly through its uncertainty term. If W4 reports a profile uncertainty that doesn't decompose this way, a
LOCK-H1 addendum fixes the mapping before S1a data are released, never afterwards. This keeps the perturbation shape from
becoming a choice made after data exist.

| id | registration input | from | into the solver |
|---|---|---|---|
| REG-GEOM | L_ch, r_in, r_out, anode position | W3 release + as-built metrology | case geometry |
| REG-BZ | B(z) at the **actual coil currents**, per configuration | S1a Hall-probe map (W4 INS-09) | tabulated profile, anode-aligned, no rescaling |
| REG-FEED | anode ṁ, composition, T_feed | W4 INS-05…07, W1 test points | propellant flow and temperature |
| REG-VD | V_d at the terminals | W4 INS-04 | discharge voltage |
| REG-PB | p_b, gauge location and calibration | W4 INS-08 | facility-mode runs only; the admissibility test TH-FAC |
| REG-DIV | f_div per reading, from the far-field sweep | W4 INS-15 | thrust observation operator T_axial = T_1D · f_div (a 1-D model can't predict divergence). Evidential cost: see VP-04 below. |
| REG-WALL | wall material | W3 | recorded; solver wall model fixed (RG-05) |

Observables use the W4 ids:

| id | class | criterion |
|---|---|---|
| VO-ID discharge current | **held out, primary, gating** | C-ID |
| VO-T thrust | **held out, primary, gating** | C-T |
| VO-IGNEXT sustainment/extinction (including the Phase 1 knee) | **held out, primary, gating** | C-SUST. Ignition is not modelled (the 1-D solver doesn't simulate breakdown), so it is recorded only. |
| VO-OSC oscillation character | held out, secondary, non-gating (VP-05) | C-OSC |
| VO-SPECIES, VO-IEDF, VO-TENE | held out, secondary, non-gating | C-DIAG. There is no pre-registered observation operator from the 1-D outlet to the far-field probe, the same reason the v1 E×B diagnostic was non-gating (VP-06). |
| VO-DIV divergence | observation operator (REG-DIV) | not predictable by a 1-D model |
| VO-BZ, VO-FEED | **registration inputs** (VP-01) | The solver takes them as boundary conditions, so it cannot predict them. B(z) measured against the W3 magnetic-circuit computation is a magnetics check, never transport evidence. |

The owner listed B(z) and the feed state among the held-out candidates. This draft proposes to reclassify them, and the
owner decides (VP-01).

**Evidential cost of the thrust operator (VP-04).** The owner also listed divergence among the held-out candidates.
Here it is used instead as an input: the measured f_div from the *same* reading multiplies T_1D. f_div depends on the
transport, so the thrust "prediction" is partly conditioned on that reading. C-T then tests the 1-D axial momentum, not
the total thrust, and **thrust is not fully held out**. A 1-D solver can't predict f_div. A fully held-out thrust test
would need a divergence model pre-registered before PF-1, and this draft has none with a source. The owner should weigh
this when counting C-T as promotion evidence.

## 5. Candidates and chemistry

- **Candidates.** The run uses exactly `sgb-screen-01`…`09` from the pinned `transport_ensemble_v0.json`, and the set is
  closed at lock. Parameters are used as recorded.
  - center_L and width_L are in channel-length units and are applied to the measured H-1 L_ch. That transfer is itself
    under test (lane 35 §4.2).
  - All nine satisfy a ≤ 1/16.
  - The candidates are hypotheses under test. They are never a performance source and never produce a design map.
- **Chemistry.** The reaction set is `abep-n2n-0.11`, with the four mandatory configs (`n2_n`, `n2_n_di_lower`,
  `n2_n_nel_wang`, `n2_n_di_lower_nel_wang`).
  - Its status is scoped to P5-N₂ validation. Using it for H-1 is an owner decision (VP-07); no chemistry change is
    proposed.
  - The five staged sensitivities play the O4 role. They never gate, but admission requires them.
- **Domain rule (not relaxed).** A run is scoreable only if f_out ≤ 1e-12 for every reaction, over every frame and cell,
  and no table is unresolved (v1 run-status rule; O2).
  - Otherwise the run is **OUT_OF_DOMAIN**: not scoreable, and not evidence against the candidate.
  - The 45 eV mean-energy cap (T_e 30 eV) stays, per A-NO.
  - Widening the domain is a controlled model-domain change with its own evidence and pre-registration. Data seen
    before that change never count as new evidence for it.
- **O₂-bearing feeds** (the OP5 air surrogate and the Phase 3 representative feed) cannot be run, because no O/O₂
  chemistry exists. They are sequestered (F5).
- **Xe on H-1** (F6) is optional (VP-12). The built-in tables have no validity manifest, and that limitation is
  recorded with any Xe score.

## 6. Condition families

| family | content | role |
|---|---|---|
| F1 | Phase 1 `hall_only` N₂ knee scan, down and up (direction rule below) | held out, mandatory |
| F2 | `hall_only` OP1/OP2/OP3/OP2H/OP3H, S2/S4/S6 | held out, mandatory |
| F3 | HW-RF/HW-ECR with the source **off** (module installed) | held out, secondary (VP-11); needs that configuration's own B(z) |
| F4 | source-**on** readings | **sequestered**, because of the inflow gap RG-03. A future pre-registration must lock before an inflow-capable model is run against them. R_arch, T and P_bus of these arms are published during the campaign, so that future use carries the flag OUTPUTS_SEEN_BEFORE_MODEL, and its evidential weight is an owner decision. |
| F5 | O₂-bearing feeds | sequestered (no O/O₂ chemistry) |
| F6 | Xe on H-1 (D-15-B health check) | optional (VP-12) |
| F7 | S5 elevated p_b | facility evidence: the TH-FAC admissibility test and the secondary mode only |

The same publication risk applies to the HW-0 families F1 and F2, whose held-out values (T, I_d, sustainment class, the
knee, R_arch) the architecture track receives and lane 25 plans to publish. Under VP-17 RELEASE_GATED they are therefore
**embargoed** until PF-1 is hash-frozen. Any disclosure before that automatically flags the affected conditions
OUTPUTS_SEEN (§10, publication rule).

**Knee-scan direction rule (PROPOSED, VP-19).** The pinned 1-D solver starts every run from a fixed initial state and has
no path memory, so it makes one prediction per level, compared with both the down and the up reading. If the measured
sustainment class of a level differs between directions (hysteresis), the level is HYSTERETIC: it is not scored for
C-SUST, C-ID or C-T, and the hysteresis is reported as a non-gating diagnostic that a path-free model cannot test. It is
neither a FAIL nor a pass. The alternative is to treat a HYSTERETIC mandatory level as a non-admissible target (candidate
INCONCLUSIVE, not FAIL).

The condition grid is **finite and enumerated at LOCK-H1** from the LOCK-1 setpoints. It includes every knee-scan level and the knee-fallback
midpoint, so that every condition is predicted before it is measured.

S1b re-mount readings come before LOCK-2. Whether PF-1 is frozen before them is VP-17. Only their dispersion statistics are released, never their means, and they are
not scored.

## 7. Modes

The **primary** mode is PROPOSED (VP-03): vacuum-mode simulation, compared with **raw** targets at base p_b. No
ingestion correction is applied to the data; the lane-25 rule is that no ingestion model rescues a class.

A target is admissible only if the S5-measured p_b sensitivity, extrapolated to zero p_b, moves the observable by less
than TH-FAC times its tolerance. Otherwise the target is TARGET_NOT_ADMISSIBLE_FACILITY.

The facility mode (ingestion on) is secondary and non-gating. The two modes are never crossed.

## 8. Acceptance criteria (forms PROPOSED; values TBD)

| criterion | form | tolerance |
|---|---|---|
| **C-ID** (gating) | \|I_d,sim − I_d,exp\| ≤ tol_Id at every mandatory condition | tol_Id = I_d,exp · ε_Id, with ε_Id ≥ k·√(u_exp,rel² + u_reg,rel²). ε_Id is the owner's value (VP-02). One option is 0.15, the project's pre-registered blind I_d scale from the P5-Xe selection record (`transport_ensemble_v0.json` `admission_rule`). Importing it is a convention, not evidence: it is not derived from H-1 uncertainty, and no P5 measurement or measurement uncertainty is a tolerance source (0.15 is a number from the P5-Xe selection record, adopted as a convention if the owner chooses it). u_exp is **TBD_FROM_INSTRUMENTATION**, and k is PROPOSED as 2. |
| **C-T** (gating) | \|T_1D·f_div − T_exp\| ≤ tol_T at every mandatory condition with an admissible reading | tol_T = k·√(u_T,exp² + (T_1D·u_f)² + u_reg,T²), with u_T,exp **TBD_FROM_INSTRUMENTATION** |
| **C-SUST** (gating) | see the three cases below | categorical |
| **C-OSC** (non-gating) | QUIET/OSCILLATORY class match, with one threshold applied identically to measured and simulated I_d(t) | threshold PROPOSED (VP-05) |
| **C-DIAG** (non-gating) | signed residuals and orderings for species, ion energy and T_e/n_e | reported only |

C-SUST cases:

- The experiment is SUSTAINED and the model goes extinct (v1 O1) → FAIL_VALIDATION / SUSTAINMENT.
- The experiment is NOT_SUSTAINED and the model is sustained → FAIL_VALIDATION / SUSTAINMENT_FALSE_POSITIVE. This is a
  PROPOSED new reason (VP-08).
- The class is MIXED (or HYSTERETIC under the F1 direction rule) → the condition is not scored for sustainment.
- The experiment is NOT_SUSTAINED and the model is extinct (VP-18 definition) → C-SUST PASS, a correct extinction
  prediction. C-ID and C-T are not scored at that condition, because there is no sustained target.
- The experiment is SUSTAINED and the model is sustained → C-SUST PASS, and C-ID and C-T are scored.

**Ambiguous classes (PROPOSED, VP-19).** A mandatory condition whose measured class is SUSTAINMENT_MIXED or HYSTERETIC is
EXCLUDED_CLASS_AMBIGUOUS. It is not scored for C-SUST, C-ID or C-T, and it is reported. It doesn't fail a candidate, and
by itself it doesn't prevent PROMOTABLE: it is skipped, not counted as a non-admissible target. The alternative is to
count it as a non-admissible target, which makes the candidate INCONCLUSIVE, not FAIL. The choice is fixed at LOCK-H1.

**Model sustainment in case (b) (PROPOSED, VP-18).** v1 O1 decides extinction relative to I_d,target, but a
NOT_SUSTAINED condition has no measured sustained I_d. The reference is therefore data-free and fixed by the grid:
I_d,ref is the time-mean PF-1 I_d of the same candidate, chemistry and configuration at the highest-flow level of the F1
scan (the scan starts at ṁ_nom). A run is model-extinct iff O1 holds with I_d,target = I_d,ref. If the model is itself
extinct at the reference level, every level of that scan is model-extinct. F2 points at V_hi use the PF-1 I_d at OP3H.
The alternative is an absolute I_d threshold in A, fixed at LOCK-H1 before data.

**Condition match.** PF-1 predictions are scored only when the measured ṁ, V_d and coil currents are within TH-COND
(TBD_FROM_INSTRUMENTATION) of the setpoint. Otherwise, the custodian gives the physics track an input-only extract. The
physics track reruns mechanically, and PF-2 is frozen before any output is released.

## 9. Run status and verdicts

- **Run status.** The run statuses are adopted by reference: PASS / FAIL_VALIDATION / OUT_OF_DOMAIN / NUMERICAL_FAILURE,
  with precedence NUMERICAL_FAILURE → OUT_OF_DOMAIN → FAIL_VALIDATION → PASS. A collapse outside the domain is
  OUT_OF_DOMAIN, not a SUSTAINMENT failure.
- **Target status.** This is measurement-side admissibility, evaluated before the model: TARGET_ADMISSIBLE, or
  NOT_ADMISSIBLE for facility, instrument, condition-mismatch or outputs-seen reasons. A non-admissible mandatory target makes the
  verdict INCONCLUSIVE, never FAIL.
- **Candidate verdict.** It covers the vacuum mode, the 4 mandatory chemistry configs and every mandatory condition.
  - **PROMOTABLE:** every run is PASS on every gating criterion with admissible targets. Conditions excluded as
    ambiguous (VP-19) are skipped under the proposed option.
  - **FAIL_VALIDATION:** at least one run is FAIL_VALIDATION.
  - **INCONCLUSIVE / NOT ELIGIBLE:** anything else. The candidate stays a screening hypothesis; it is not rejected.
  - There is one nominal registration per configuration, so there is no "some layer-1 member passes" quantifier. By
    construction this is stricter than v1 D5.
- **Campaign verdict.** PASS if at least one candidate is PROMOTABLE; FAIL if all candidates are FAIL_VALIDATION;
  otherwise INCONCLUSIVE.
- **PROMOTABLE never admits.** Admission also needs:
  - every staged sensitivity and triggered escalation, scored and dispositioned by the owner;
  - an admission record (the O4 gate).

  The O4 tooling is P5-N₂-specific today, and adapting it is outside this lane.
- **The outcome is permanent**, like v1's.
- **Reruns.** NUMERICAL_FAILURE runs are never rerun with changed numerics. Only an infrastructure crash may be rerun,
  with byte-identical inputs, and the rerun is logged.

## 10. Custody, blinding and hash lock

The roles are:

- **OWNER.**
- **DATA_CUSTODIAN:** designated by the owner, and not a physics-track modeller.
- **EXPERIMENT_TEAM.**
- **ARCHITECTURE_TRACK:** receives R_arch, T, P_bus and sustainment classes for its stop rules, and does not pass
  held-out outputs to the physics track. It is bound by the publication rule below.
- **PHYSICS_TRACK:** sees registration inputs only, until scoring.

The sequence is:

1. **K0.** This draft goes to the owner, who decides VP-01…VP-20.
2. **K1, LOCK-H1.** Records the sha256 of the criteria, rules, candidate set, chemistry configs, numerics, prediction
   and scoring scripts, and the condition grid. It happens before the custodian releases any S1a registration input,
   and therefore before any Hall-on reading of H-1.
3. **K2.** S1a runs without plasma. The custodian then releases the registration inputs.
4. **K3, blind prediction PF-1.** Covers all candidates × mandatory chemistry × the full grid, plus the u_reg runs and
   the staged sensitivities. PF-1 is hash-frozen and recorded in the trigger ledger. The freeze point is owner decision
   **VP-17**:
   - **RELEASE_GATED (PROPOSED):** PF-1 is frozen before the custodian releases any held-out output to the physics
     track (at the latest K6). The hardware schedule is not held; blinding rests on custody and the leak rule.
   - **HOLD_S1B (alternative):** PF-1 is frozen **before the first Hall-on reading (S1b)**, and S1b waits for it. The
     predictions then exist before the measurements do, at the cost of putting a campaign of order v1 size
     (9 × 4 × N_cond nominal runs, plus 2 × N_reg u_reg runs per nominal run, plus the staged sensitivities) on the
     hardware critical path.
   - **What the owner should know.** The *criteria* are locked before any measurement under both options. Only
     HOLD_S1B makes the *predictions* strictly precede the measurements, which is the literal reading of D-14-B and of
     Question A rule 2 ("pre-registered before measurement"). Under RELEASE_GATED, the held-out readings exist before
     PF-1 and their blindness rests on custody and the publication embargo alone.
   - **Late PF-1, either option:** the held-out release, and so scoring, waits. No condition is dropped or added because
     PF-1 is late. Under HOLD_S1B the owner may instead switch the whole campaign to RELEASE_GATED by a dated addendum
     recorded before S1b, never per condition and never after a Hall-on reading.
5. **K4.** S1b runs. The custodian releases dispersion statistics only. LOCK-H2 adds the audited uncertainties through
   the LOCK-H1 formulas, without discretion.
6. **K5.** S2…S6 run. A condition-mismatched reading goes through an input-only extract, and PF-2 is frozen.
7. **K6.** The raw dataset is frozen (sha256). The held-out outputs are released to the frozen scoring script, which
   scores once. The mechanical decision file goes to the owner.

**Publication rule (PROPOSED, part of RELEASE_GATED).** The architecture track legitimately receives HW-0 values, and
lane 25 plans to publish R_arch (its denominator is HW-0), the Phase 1 knee (which sets OP2/OP2H), and per-point I_d
traces, divergence and B(z) (M8, M11). The OD also requires a Phase 3 absolute T_measured demonstration during the
campaign. Once a value is published, nobody can verify that it didn't reach the physics track. So:

- **Embargo.** No HW-0 held-out value of F1/F2 (or F3/F6 if mandatory), and no quantity derived from one, is published or
  disclosed outside {custodian, experiment team, architecture track, owner} until PF-1 is hash-frozen. This covers I_d,
  T, P_bus, sustainment class, the knee and the OP2/OP2H setpoints it fixes, R_arch, I_d traces, species, ion energy and
  T_e/n_e. It applies to stop-rule disclosures, milestone bundles, Phase 3 reports and repository commits the physics
  track can read.
- **Automatic flag.** If such a value is disclosed before PF-1 is frozen, by choice (for example to meet a Milestone A
  date) or by error, every condition whose value, or any input of a derived quantity, was disclosed is flagged
  OUTPUTS_SEEN automatically, as F4 is. For R_arch and the knee, that means every condition entering them. The flag does
  not depend on showing that the value reached the physics track. The target becomes TARGET_NOT_ADMISSIBLE_OUTPUTS_SEEN,
  so the candidate is INCONCLUSIVE, not FAIL.
- **Release log.** The custodian logs every release and disclosure. At K6 the log is compared mechanically with the PF-1
  freeze time. PF-2 input-only extracts are produced only after PF-1 is frozen.

Under HOLD_S1B this rule is unnecessary, because PF-1 is frozen before any Hall-on reading.

**Leaks.** If a held-out output reaches the physics track early, or is disclosed outside the custody circle before PF-1
is frozen, the custodian records it. Predictions frozen before the
leak stay valid. A prediction frozen after it, for the leaked condition, is flagged OUTPUTS_SEEN and cannot support
PROMOTABLE for that condition.

**Changes after lock.** Any change after LOCK-H1 is a dated addendum, never an edit. No PF-1 run and no score-bearing
run may take place before LOCK-H1. The PROPOSED lock location is `docs/validation/hall_transport_v2_prereg/lock/`
(VP-15); this draft does not create it.

## 11. Runnability dependencies

These are this draft's own gates; only some of them map to lane-35 items (noted in the table).
The campaign is **NOT_RUNNABLE** until the following hold:

| gate | requirement |
|---|---|
| RG-01 | H-1 geometry released and measured (W3 HW-H1-03; lane 35 P6) |
| RG-02 | S1a B(z) measured at the actual coil currents |
| RG-03 | Hall-map inflow gap at `HALL_INLET_Z0` (lane 17 §8; lane 35 open decision 10). Blocks **only** source-on family F4; not required before PF-1 |
| RG-04 | numerics fixed for H-1, and a data-free grid-adequacy check (lane 35 open decision 7) |
| RG-05 | wall model and `ion_wall_losses` (lane 35 open decision 3; PROPOSED: as in v1) |
| RG-06 / VP-07 | chemistry acceptance for H-1 |
| RG-07a | W4 audited uncertainties of the registration inputs (needed by the u_reg rule); required before PF-1 |
| RG-07b | W4 audited uncertainties of the held-out observables; required only before LOCK-H2 |
| RG-08 | W1 test points and LOCK-1 setpoints |
| RG-09 | LOCK-1 adopts D-14-B |
| RG-10 | frozen prediction and scoring scripts |
| RG-11 | cathode boundary rule (see the warning below) |
| RG-12 | pin unchanged |

RG-07 is split. **RG-07a**, the W4 audited uncertainties of the registration inputs, is required before PF-1,
because the u_reg rule perturbs each registration input by that uncertainty. **RG-07b**, the audited uncertainties of
the held-out observables, is needed only before LOCK-H2.

**RG-03**, the Hall-map inflow gap (lane 17 §8; lane 35 open decision 10), blocks only the source-on family F4. The
`hall_only` families can run without it.

**Cathode boundary warning (RG-11, VP-10).** The PROPOSED option keeps the lane-17 §10 solver settings, including a
cathode coupling voltage of 0.0 V. Lane 17 itself calls that value a **placeholder solver setting, not a design value**
(`hall_reference_v1.json`, INV-C2). Keeping it makes the gating I_d and thrust predictions depend on a boundary value
with no hardware basis, so a FAIL_VALIDATION could reflect the placeholder rather than the transport closure. The
alternative, the measured cathode-to-ground potential per reading as a registration input, removes the placeholder. Its
mapping to the solver boundary would be fixed at LOCK-H1. The owner should choose knowingly.

## 12. Forecast risk and the legitimate response

In v1, 66 % of run-readings were OUT_OF_DOMAIN. H-1 may reach similar T_e, which would leave every candidate INCONCLUSIVE
whatever the data show. A data-free blind state envelope, run before LOCK-H1 on the W3 design geometry and computed
B(z) (not PF-1 and not score-bearing), reveals this before any data exist.

The PROPOSED response (VP-09) is that, before LOCK-H1 and without data, the owner may add held-out conditions chosen from
the candidates' data-free blind state envelope. Choosing conditions from data-free model output is experimental design,
not tuning. Relaxing f_out or the 45 eV cap is **not** a legitimate response.

## 13. Owner decisions (all PROPOSED)

| id | question | proposed answer |
|---|---|---|
| VP-01 | B(z) and feed state as registration inputs | yes |
| VP-02 | I_d tolerance form and ε_Id | owner value; one option is 0.15, imported as a convention, not evidence (no P5 measurement or uncertainty is a tolerance source) |
| VP-03 | primary vacuum-vs-raw with TH-FAC | yes |
| VP-04 | thrust operator uses the measured f_div | yes; cost: thrust then not fully held out (§4) |
| VP-05 | oscillation class | non-gating |
| VP-06 | species and ion energy | non-gating unless an operator is pre-registered |
| VP-07 | accept `abep-n2n-0.11` for H-1 | owner decision |
| VP-08 | SUSTAINMENT_FALSE_POSITIVE reason | yes |
| VP-09 | data-free, domain-aware conditions before lock | yes |
| VP-10 | cathode boundary | as lane 17 §10; **warning**: 0.0 V coupling is a lane-17 placeholder (§11) |
| VP-11 | F3 | secondary |
| VP-12 | F6 (Xe) | secondary |
| VP-13 | k | 2 |
| VP-14 | custodian | owner designates |
| VP-15 | lock location | as proposed above |
| VP-16 | O4-equivalent escalation fractions | 0.5 × tolerance |
| VP-17 | PF-1 freeze point | RELEASE_GATED with the publication embargo (alternative HOLD_S1B, the only option where predictions strictly precede measurements; §10) |
| VP-18 | reference I_d for model sustainment in C-SUST case (b) | data-free PF-1 reference at the highest-flow scan level (§8) |
| VP-19 | ambiguous sustainment class (hysteresis, MIXED) | excluded, not scored, skipped for PROMOTABLE (§6, §8) |
| VP-20 | u_reg perturbation of profile inputs | scalars separately; B(z) amplitude scale and axial shift (§4) |

## 14. Numbers and their sources

Every number is listed in the JSON `thresholds` and `numbers_used` sections with its status (RFP /
PRE_REGISTERED_PROJECT_RULE / PROPOSED / TBD_FROM_INSTRUMENTATION) and source:

| number | source |
|---|---|
| 12–25 mN, < 1.5 kW | RFP (context only) |
| f_out 1e-12 | v1 run-status rule |
| 45 eV / 30 eV | `PINNED.toml`, A-NO |
| a ≤ 1/16 | `transport_ensemble_v0.json` |
| 9 candidates | ensemble file |
| 66 %, 1080 runs | CLAUDE.md gate 3, context only |
| 0.15 (ε_Id option) | `transport_ensemble_v0.json` `admission_rule` (15 % blind criterion); convention only |
| 5 knee levels | lane 25 T-KNEE-LEVELS, PROPOSED there |
| sha256 digests | `pin_inputs.py` |

No literature value, instrument accuracy or physical constant is introduced by this draft.
