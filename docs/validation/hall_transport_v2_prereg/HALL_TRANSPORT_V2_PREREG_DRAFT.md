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
| **A** conditional selection | Not required, and does not block A. LOCK-1 adopting package decision D-14-B costs no readings. | nothing from this lane |
| **B** physics-backed selection | **Primary.** In this set of workstreams, this is the only route by which a closure can be *admitted*. | owner decisions VP-01…VP-16; W4 audited uncertainties; W3 H-1 geometry release; S1a B(z); the lane-35 items RG-01…RG-12; LOCK-H1; a PROMOTABLE outcome; O4-equivalent dispositions; an admission record. For `rf_hall`/`ecr_hall` absolute performance, also the inflow model change at `HALL_INLET_Z0` and O/O₂ chemistry. |
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
Instead, each input's measurement uncertainty is propagated **blind**, before any data, into a model-side u_reg. Each
input is perturbed by ± its standard uncertainty, one at a time, and u_reg is the root-sum-square of the half-differences
per observable.

| id | registration input | from | into the solver |
|---|---|---|---|
| REG-GEOM | L_ch, r_in, r_out, anode position | W3 release + as-built metrology | case geometry |
| REG-BZ | B(z) at the **actual coil currents**, per configuration | S1a Hall-probe map (W4 INS-09) | tabulated profile, anode-aligned, no rescaling |
| REG-FEED | anode ṁ, composition, T_feed | W4 INS-05…07, W1 test points | propellant flow and temperature |
| REG-VD | V_d at the terminals | W4 INS-04 | discharge voltage |
| REG-PB | p_b, gauge location and calibration | W4 INS-08 | facility-mode runs only; the admissibility test TH-FAC |
| REG-DIV | f_div per reading, from the far-field sweep | W4 INS-15 | thrust observation operator T_axial = T_1D · f_div (a 1-D model can't predict divergence) |
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
| F1 | Phase 1 `hall_only` N₂ knee scan, down and up | held out, mandatory |
| F2 | `hall_only` OP1/OP2/OP3/OP2H/OP3H, S2/S4/S6 | held out, mandatory |
| F3 | HW-RF/HW-ECR with the source **off** (module installed) | held out, secondary (VP-11); needs that configuration's own B(z) |
| F4 | source-**on** readings | **sequestered**, because of the inflow gap RG-03. A future pre-registration must lock before an inflow-capable model is run against them. R_arch, T and P_bus of these arms are published during the campaign, so that future use carries the flag OUTPUTS_SEEN_BEFORE_MODEL, and its evidential weight is an owner decision. |
| F5 | O₂-bearing feeds | sequestered (no O/O₂ chemistry) |
| F6 | Xe on H-1 (D-15-B health check) | optional (VP-12) |
| F7 | S5 elevated p_b | facility evidence: the TH-FAC admissibility test and the secondary mode only |

The condition grid is **finite and enumerated at LOCK-H1**. It includes every knee-scan level and the knee-fallback
midpoint, so that every condition is predicted before it is measured.

S1b re-mount readings come before LOCK-2. Only their dispersion statistics are released, never their means, and they are
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
| **C-ID** (gating) | \|I_d,sim − I_d,exp\| ≤ tol_Id at every mandatory condition | tol_Id = I_d,exp · ε_Id, with ε_Id ≥ k·√(u_exp,rel² + u_reg,rel²). ε_Id is the owner's value (VP-02). One option is 0.15, the project's pre-registered blind I_d scale; it is not derived from H-1 uncertainty. u_exp is **TBD_FROM_INSTRUMENTATION**, and k is PROPOSED as 2. |
| **C-T** (gating) | \|T_1D·f_div − T_exp\| ≤ tol_T at every mandatory condition with an admissible reading | tol_T = k·√(u_T,exp² + (T_1D·u_f)² + u_reg,T²), with u_T,exp **TBD_FROM_INSTRUMENTATION** |
| **C-SUST** (gating) | see the three cases below | categorical |
| **C-OSC** (non-gating) | QUIET/OSCILLATORY class match, with one threshold applied identically to measured and simulated I_d(t) | threshold PROPOSED (VP-05) |
| **C-DIAG** (non-gating) | signed residuals and orderings for species, ion energy and T_e/n_e | reported only |

C-SUST cases:

- The experiment is SUSTAINED and the model goes extinct (v1 O1) → FAIL_VALIDATION / SUSTAINMENT.
- The experiment is NOT_SUSTAINED and the model is sustained → FAIL_VALIDATION / SUSTAINMENT_FALSE_POSITIVE. This is a
  PROPOSED new reason (VP-08).
- The class is MIXED → the condition is not scored for sustainment.

**Condition match.** PF-1 predictions are scored only when the measured ṁ, V_d and coil currents are within TH-COND
(TBD_FROM_INSTRUMENTATION) of the setpoint. Otherwise, the custodian gives the physics track an input-only extract. The
physics track reruns mechanically, and PF-2 is frozen before any output is released.

## 9. Run status and verdicts

- **Run status.** The run statuses are adopted by reference: PASS / FAIL_VALIDATION / OUT_OF_DOMAIN / NUMERICAL_FAILURE,
  with precedence NUMERICAL_FAILURE → OUT_OF_DOMAIN → FAIL_VALIDATION → PASS. A collapse outside the domain is
  OUT_OF_DOMAIN, not a SUSTAINMENT failure.
- **Target status.** This is measurement-side admissibility, evaluated before the model: TARGET_ADMISSIBLE, or
  NOT_ADMISSIBLE for facility, instrument or condition-mismatch reasons. A non-admissible mandatory target makes the
  verdict INCONCLUSIVE, never FAIL.
- **Candidate verdict.** It covers the vacuum mode, the 4 mandatory chemistry configs and every mandatory condition.
  - **PROMOTABLE:** every run is PASS on every gating criterion with admissible targets.
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
  held-out outputs to the physics track.
- **PHYSICS_TRACK:** sees registration inputs only, until scoring.

The sequence is:

1. **K0.** This draft goes to the owner, who decides VP-01…VP-16.
2. **K1, LOCK-H1.** Records the sha256 of the criteria, rules, candidate set, chemistry configs, numerics, prediction
   and scoring scripts, and the condition grid. It happens before any Hall-on reading of H-1.
3. **K2.** S1a runs without plasma. The custodian then releases the registration inputs.
4. **K3, blind prediction PF-1.** Covers all candidates × mandatory chemistry × the full grid, plus the u_reg runs and
   the staged sensitivities. PF-1 is hash-frozen and recorded in the trigger ledger **before the first Hall-on reading
   (S1b)**. The predictions therefore exist before the measurements do.
5. **K4.** S1b runs. The custodian releases dispersion statistics only. LOCK-H2 adds the audited uncertainties through
   the LOCK-H1 formulas, without discretion.
6. **K5.** S2…S6 run. A condition-mismatched reading goes through an input-only extract, and PF-2 is frozen.
7. **K6.** The raw dataset is frozen (sha256). The held-out outputs are released to the frozen scoring script, which
   scores once. The mechanical decision file goes to the owner.

**Leaks.** If a held-out output reaches the physics track early, the custodian records it. Predictions frozen before the
leak stay valid. A prediction frozen after it, for the leaked condition, is flagged OUTPUTS_SEEN and cannot support
PROMOTABLE for that condition.

**Changes after lock.** Any change after LOCK-H1 is a dated addendum, never an edit. No PF-1 run and no score-bearing
run may take place before LOCK-H1. The PROPOSED lock location is `docs/validation/hall_transport_v2_prereg/lock/`
(VP-15); this draft does not create it.

## 11. Runnability dependencies

The campaign is **NOT_RUNNABLE** until the following hold:

| gate | requirement |
|---|---|
| RG-01 | H-1 geometry released and measured (W3 HW-H1-03; lane 35 P6) |
| RG-02 | S1a B(z) measured at the actual coil currents |
| RG-04 | numerics fixed for H-1, and a data-free grid-adequacy check (lane 35 open decision 7) |
| RG-05 | wall model and `ion_wall_losses` (lane 35 open decision 3; PROPOSED: as in v1) |
| RG-06 / VP-07 | chemistry acceptance for H-1 |
| RG-08 | W1 test points and LOCK-1 setpoints |
| RG-09 | LOCK-1 adopts D-14-B |
| RG-10 | frozen prediction and scoring scripts |
| RG-11 | cathode boundary rule |
| RG-12 | pin unchanged |

RG-07, the W4 uncertainties, is needed before LOCK-H2.

**RG-03**, the Hall-map inflow gap (lane 17 §8; lane 35 open decision 10), blocks only the source-on family F4. The
`hall_only` families can run without it.

## 12. Forecast risk and the legitimate response

In v1, 66 % of run-readings were OUT_OF_DOMAIN. H-1 may reach similar T_e, which would leave every candidate INCONCLUSIVE
whatever the data show. PF-1 reveals this before any data exist.

The PROPOSED response (VP-09) is that, before LOCK-H1 and without data, the owner may add held-out conditions chosen from
the candidates' data-free blind state envelope. Choosing conditions from data-free model output is experimental design,
not tuning. Relaxing f_out or the 45 eV cap is **not** a legitimate response.

## 13. Owner decisions (all PROPOSED)

| id | question | proposed answer |
|---|---|---|
| VP-01 | B(z) and feed state as registration inputs | yes |
| VP-02 | I_d tolerance form and ε_Id | owner value; one option is 0.15 |
| VP-03 | primary vacuum-vs-raw with TH-FAC | yes |
| VP-04 | thrust operator uses the measured f_div | yes |
| VP-05 | oscillation class | non-gating |
| VP-06 | species and ion energy | non-gating unless an operator is pre-registered |
| VP-07 | accept `abep-n2n-0.11` for H-1 | owner decision |
| VP-08 | SUSTAINMENT_FALSE_POSITIVE reason | yes |
| VP-09 | data-free, domain-aware conditions before lock | yes |
| VP-10 | cathode boundary | as lane 17 §10 |
| VP-11 | F3 | secondary |
| VP-12 | F6 (Xe) | secondary |
| VP-13 | k | 2 |
| VP-14 | custodian | owner designates |
| VP-15 | lock location | as proposed above |
| VP-16 | O4-equivalent escalation fractions | 0.5 × tolerance |

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
| 5 knee levels | lane 25 T-KNEE-LEVELS, PROPOSED there |
| sha256 digests | `pin_inputs.py` |

No literature value, instrument accuracy or physical constant is introduced by this draft.
